import numpy as np
from numpy import inf
import itertools
import keras
import matplotlib
import matplotlib.pyplot as plt
from sklearn import preprocessing, svm
from sklearn.metrics import roc_auc_score, roc_curve, auc, confusion_matrix
from sklearn.model_selection import train_test_split
from IPython.display import FileLink, FileLinks
from keras.models import Sequential
from keras.layers import Dense, Dropout, BatchNormalization
from keras.utils import to_categorical, plot_model
from keras.callbacks import History, ModelCheckpoint, ReduceLROnPlateau
from keras.optimizers import Adam

from ROOT import TCanvas, TFile, TH1F, TH2F, gROOT, kRed, kBlue, kGreen, kMagenta, kCyan, gStyle
from ROOT import gErrorIgnoreLevel
from ROOT import kInfo, kWarning, kError

import math
import pickle
import sys

def dict_to_str(parameters):
    layers_str = [str(parameters['layers'][i]) for i in range(len(parameters['layers']))]
    tag = 'layers_'
    for i in range(len(layers_str)):
        tag = tag + layers_str[i]
        if i < len(layers_str)-1: tag = tag + '_'
    tag = tag + '__batchsize_' + str(parameters['batchsize'])
    tag = tag + '__sampleclasses_' + str(len(parameters['sampleclasses'])) + '_'
    for i in range(len(parameters['sampleclasses'])):
        for j in range(len(parameters['sampleclasses'][i])):
            tag = tag + parameters['sampleclasses'][i][j]
            if j < len(parameters['sampleclasses'][i]) - 1:
                tag = tag + '+'
        if i < len(parameters['sampleclasses']) - 1:
            tag = tag + '_'

    tag = tag + '__dropoutrate_' + '{num:03d}'.format(num=int(parameters['dropoutrate']*100.))
    tag = tag + '__epochs_' + str(parameters['epochs'])
    tag = tag + '__runonfullsample_' + str(parameters['runonfullsample'])
    tag = tag + '__equallyweighted_' + str(parameters['equallyweighted'])
    if len(tag.split('__')) != len(parameters): raise ValueError('in dict_to_str: Number of parameters given in the dictionary does no longer match the prescription how to build the tag out of it.')
    return tag

def get_classes_tag(parameters):
    tag = 'sampleclasses_' + str(len(parameters['sampleclasses'])) + '_'
    for i in range(len(parameters['sampleclasses'])):
        for j in range(len(parameters['sampleclasses'][i])):
            tag = tag + parameters['sampleclasses'][i][j]
            if j < len(parameters['sampleclasses'][i]) - 1:
                tag = tag + '+'
        if i < len(parameters['sampleclasses']) - 1:
            tag = tag + '_'
    return tag

def get_classtitles(parameters):
    classes = parameters['sampleclasses']
    classtitles = {}
    for key in classes.keys():
        list = classes[key]
        title = ''
        for i in range(len(list)):
            title = title + list[i]
            if i < len(list)-1:
                title = title + '+'
        classtitles[key] = title
    return classtitles


def slim_frp_tpr_thr(FalsePositiveRates, TruePositiveRates, Thresholds):
    idxlist = []
    idx=0
    keepgoing = True
    npoints = 10000
    stepsize = int(float(len(FalsePositiveRates))/float(npoints))
    for idx in range(npoints-1):
        if FalsePositiveRates[idx*stepsize] - FalsePositiveRates[(idx+1)*stepsize] < -5e-6:
            idxlist.append(idx*stepsize)

    if FalsePositiveRates[idxlist[len(idxlist)-1]] - FalsePositiveRates[len(FalsePositiveRates)-1] < -5e-6: idxlist.append(len(FalsePositiveRates)-1)

    FalsePositiveRates = FalsePositiveRates[idxlist]
    TruePositiveRates = TruePositiveRates[idxlist]
    Thresholds = Thresholds[idxlist]
    return FalsePositiveRates, TruePositiveRates, Thresholds


def get_fpr_tpr_thr_auc(parameters, pred_val, labels_val, weights_val):

    equallyweighted = parameters['equallyweighted']
    FalsePositiveRates = {}
    TruePositiveRates = {}
    Thresholds = {}
    aucs = {}
    for i in range(labels_val.shape[1]):

        FalsePositiveRates[i], TruePositiveRates[i], Thresholds[i] = roc_curve(labels_val[:,i], pred_val[:,i], sample_weight=weights_val)
        FalsePositiveRates[i], TruePositiveRates[i], Thresholds[i] = slim_frp_tpr_thr(FalsePositiveRates=FalsePositiveRates[i], TruePositiveRates=TruePositiveRates[i], Thresholds=Thresholds[i])
        aucs[i] = auc(FalsePositiveRates[i], TruePositiveRates[i])
    return FalsePositiveRates, TruePositiveRates, Thresholds, aucs


def get_data_dictionaries(parameters, eventweights_train, sample_weights_train, pred_train, labels_train, eventweights_val, sample_weights_val, pred_val, labels_val):
    classes = parameters['sampleclasses']
    equallyweighted = parameters['equallyweighted']
    pred_trains = {}
    pred_vals = {}
    weights_trains = {}
    weights_vals = {}
    normweights_trains = {}
    normweights_vals = {}
    lumiweights_trains = {}
    lumiweights_vals = {}

    for cl in classes.keys():
        pred_trains_thistrueclass = {}
        pred_vals_thistrueclass = {}
        weights_trains_thistrueclass = {}
        weights_vals_thistrueclass = {}
        normweights_trains_thistrueclass = {}
        normweights_vals_thistrueclass = {}
        lumiweights_trains_thistrueclass = {}
        lumiweights_vals_thistrueclass = {}
        for node in classes.keys():
            if not equallyweighted:
                weights_trains_thistrueclass[node] = eventweights_train[labels_train[:,cl] == 1]
                weights_vals_thistrueclass[node] = eventweights_val[labels_val[:,cl] == 1]
            else:
                weights_trains_thistrueclass[node] = sample_weights_train[labels_train[:,cl] == 1]
                weights_vals_thistrueclass[node]   = sample_weights_val[labels_val[:,cl] == 1]

            pred_trains_thistrueclass[node] = pred_train[:,node][labels_train[:,cl] == 1]
            pred_vals_thistrueclass[node] = pred_val[:,node][labels_val[:,cl] == 1]
            lumiweights_trains_thistrueclass[node] = eventweights_train[labels_train[:,cl] == 1]
            lumiweights_vals_thistrueclass[node] = eventweights_val[labels_val[:,cl] == 1]
            sum_train = weights_trains_thistrueclass[node].sum()
            sum_val   = weights_vals_thistrueclass[node].sum()
            normweights_trains_thistrueclass[node] = np.array([1./sum_train for j in range(weights_trains_thistrueclass[node].shape[0])])
            normweights_vals_thistrueclass[node]   = np.array([1./sum_val for j in range(weights_vals_thistrueclass[node].shape[0])])

        pred_trains[cl] = pred_trains_thistrueclass
        pred_vals[cl] = pred_vals_thistrueclass
        weights_trains[cl] = weights_trains_thistrueclass
        weights_vals[cl] = weights_vals_thistrueclass
        normweights_trains[cl] = normweights_trains_thistrueclass
        normweights_vals[cl] = normweights_vals_thistrueclass
        lumiweights_trains[cl] = lumiweights_trains_thistrueclass
        lumiweights_vals[cl] = lumiweights_vals_thistrueclass
    return pred_trains, weights_trains, normweights_trains, lumiweights_trains, pred_vals, weights_vals, normweights_vals, lumiweights_vals


def hinton(matrix, max_weight=None, ax=None):
    """Draw Hinton diagram for visualizing a weight matrix."""
    ax = ax if ax is not None else plt.gca()

    if not max_weight:
        max_weight = 2 ** np.ceil(np.log(np.abs(matrix).max()) / np.log(2))

    ax.patch.set_facecolor('gray')
    ax.set_aspect('equal', 'box')
    ax.xaxis.set_major_locator(plt.NullLocator())
    ax.yaxis.set_major_locator(plt.NullLocator())

    for (x, y), w in np.ndenumerate(matrix):
        color = 'white' if w > 0 else 'black'
        size = np.sqrt(np.abs(w) / max_weight)
        rect = plt.Rectangle([x - size / 2, y - size / 2], size, size,
                             facecolor=color, edgecolor=color)
        ax.add_patch(rect)

    ax.autoscale_view()
    ax.invert_yaxis()


def conf_matrix(labels, predictions, weights):
    # will return a list of lists, shape=NxN
    # each list is for one true class
    if labels.shape != predictions.shape:
        raise ValueError('Labels and predictions do not have the same shape.')
    if labels.shape[0] != weights.shape[0]:
        raise ValueError('Labels and weights do not have the same length (.shape[0]).')

    # initialize confusion matrix
    matrix = np.zeros((labels.shape[1], labels.shape[1]))

    # format inputs
    for i in range(labels.shape[0]):
        label = -1
        predclass = -1
        maxpred = -1
        for j in range(labels.shape[1]):
            if labels[i,j] == 1: label = j
            if maxpred < predictions[i,j]:
                maxpred = predictions[i,j]
                predclass = j
        if label == -1: raise ValueError('For this event, the labels of all classes are 0, so the event doesn\'t have a class?')
        matrix[label,predclass] = matrix[label,predclass] + weights[i]

    return matrix



def plot_confusion_matrix(cm, classes,
                          normalize=False,
                          title='Confusion matrix',
                          cmap=plt.cm.Blues):
    """
    This function prints and plots the confusion matrix.
    Normalization can be applied by setting `normalize=True`.
    """
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        print("Normalized confusion matrix")
    else:
        print('Confusion matrix, without normalization')

    plt.imshow(cm, interpolation='none', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    listofclasses = []
    for key in classes.keys():
        listofclasses.append(classes[key])
    plt.xticks(tick_marks, listofclasses, rotation=45)
    plt.yticks(tick_marks, listofclasses)

    # fmt = '.2f' if normalize else 'd'
    fmt = '.2f'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if cm[i, j] > thresh else "black")

    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()

def log_model_performance(parameters, model_history, aucs):
    loss_train = model_history['loss']
    loss_val = model_history['val_loss']
    acc_train = model_history['categorical_accuracy']
    acc_val = model_history['val_categorical_accuracy']
    tag = dict_to_str(parameters)
    aucs_str = ''
    for i in range(len(aucs)):
        aucs_str = aucs_str + '{0:1.3f}'.format(aucs[i])
        if i < len(aucs)-1: aucs_str = aucs_str + ', '
    with open('output/'+tag+'/ModelPerformance.txt', 'w') as f:
        f.write('\n\n====================\n')
        f.write('Tag: %s\n\n' % (tag))
        f.write('Parameters: [layers], batchsize, sampleclasses, dropoutrate*100, epochs, runonfullsample, equallyweighted\n')
        parameterstring = str(parameters['layers']) + ', ' + str(parameters['batchsize']) + ', '
        for i in range(len(parameters['sampleclasses'])):
            for j in range(len(parameters['sampleclasses'][i])):
                parameterstring = parameterstring + parameters['sampleclasses'][i][j]
                if j < len(parameters['sampleclasses'][i]) - 1:
                    parameterstring = parameterstring + '+'
            if i < len(parameters['sampleclasses']) - 1:
                parameterstring = parameterstring + ' -- '
        parameterstring = parameterstring + ', {num:03d}, '.format(num=int(parameters['dropoutrate']*100.)) + str(parameters['epochs']) + ', ' + str(parameters['runonfullsample']) + ', ' + str(parameters['equallyweighted'])
        f.write(parameterstring + '\n\n')
        f.write('AUCs: %s\n' % (aucs_str))
        f.write('Performance: training loss (min, final) -- validation loss (min, final) -- training acc (min, final) -- validation acc (min, final)\n')
        f.write('                         ({0:2.3f}, {1:2.3f}) --               ({2:2.3f}, {3:2.3f}) --            ({4:1.3f}, {5:1.3f}) --              ({6:1.3f}, {7:1.3f})\n'.format(min(loss_train), loss_train[len(loss_train)-1], min(loss_val), loss_val[len(loss_val)-1], min(acc_train), acc_train[len(acc_train)-1], min(acc_val), acc_val[len(acc_val)-1]))


def plot_roc(parameters, FalsePositiveRates, TruePositiveRates, aucs, colorstr, outnametag):
    print 'Starting to plot ROC'
    tag = dict_to_str(parameters)
    classtitles = get_classtitles(parameters)
    plt.clf()
    fig = plt.figure()
    plt.xticks(np.arange(0.1,1.1,0.1))
    plt.grid(True, which='both')
    for i in range(len(FalsePositiveRates)):
        plt.semilogy(TruePositiveRates[i], FalsePositiveRates[i], label=classtitles[i] + ', AUC: '+str(round(aucs[i],3)), color=colorstr[i])
    plt.legend(loc='best')
    plt.ylim([0.0001, 1.05])
    plt.xlabel('Class selection efficiency')
    plt.ylabel('Class background efficiency')
    fig.savefig('Plots/'+tag+'/ROC_'+outnametag+'.pdf')
    plt.close()




def plot_loss(parameters, model_history):
    print 'Starting to plot Loss'
    tag = dict_to_str(parameters)
    plt.clf()
    fig = plt.figure()
    plt.grid()
    plt.plot(model_history['loss'], label = 'Training set')
    plt.plot(model_history['val_loss'], label = 'Validation set')
    plt.legend(loc='best')
    plt.ylabel('Loss')
    plt.xlabel('Number of training epochs')
    fig.savefig('Plots/'+tag+'/Loss.pdf')
    plt.close()


def plot_accuracy(parameters, model_history):
    print 'Starting to plot accuracy'
    tag = dict_to_str(parameters)
    plt.clf()
    fig = plt.figure()
    plt.grid()
    plt.plot(model_history['categorical_accuracy'], label = 'Training set')
    plt.plot(model_history['val_categorical_accuracy'], label = 'Validation set')
    plt.legend(loc='best')
    plt.ylim([0., 1.05])
    plt.ylabel('Prediction accuracy')
    plt.xlabel('Number of training epochs')
    fig.savefig('Plots/'+tag+'/Accuracy.pdf')


def plot_weights(parameters, model):
    print 'Starting to plot weights'
    tag = dict_to_str(parameters)
    for i in range(len(model.layers)):
        try:
            W = model.layers[i].kernel.get_value(borrow=True)
        except AttributeError:
            continue
        W = model.layers[i].kernel.get_value(borrow=True)
        W = np.squeeze(W)
        print W.shape

        plt.clf()
        fig = plt.figure(figsize=[20.,20.], dpi=10000)
        hinton(W)
        fig.savefig('Plots/'+tag+'/Weights_layer'+str(i)+'.pdf')

        plt.clf()
        fig = plt.figure(dpi=500)
        im = plt.imshow(W, cmap='viridis', interpolation='none')
        fig.colorbar(im)
        fig.savefig('Plots/'+tag+'/Weights_layer'+str(i)+'_color.pdf')


def plot_confusion_matrices(parameters, pred_train, labels_train, sample_weights_train, eventweights_train, pred_val, labels_val, sample_weights_val, eventweights_val):
    print 'Starting to plot confusion matrix'
    tag = dict_to_str(parameters)
    equallyweighted = parameters['equallyweighted']
    classtitles = get_classtitles(parameters)

    labels_1d = np.empty(labels_val.shape[0])
    pred_1d = np.empty(pred_val.shape[0])
    for i in range(len(labels_1d)):
        label = -1
        predclass = -1
        maxpred = -1
        for j in range(labels_val.shape[1]):
            if labels_val[i,j] == 1: label = j
            if maxpred < pred_val[i,j]:
                maxpred = pred_val[i,j]
                predclass = j
        if label == -1: raise ValueError('For this event, the labels of all classes are 0, so the event doesn\'t have a class?')
        labels_1d[i] = label
        pred_1d[i] = predclass
    if equallyweighted:
        conf_matrix_train = conf_matrix(labels_train, pred_train, sample_weights_train)
        conf_matrix_val = conf_matrix(labels_val, pred_val, sample_weights_val)
    else:
        conf_matrix_train = conf_matrix(labels_train, pred_train, eventweights_train)
        conf_matrix_val = conf_matrix(labels_val, pred_val, eventweights_val)


    plt.clf()
    fig = plt.figure()
    plot_confusion_matrix(conf_matrix_val, classes=classtitles, title='Confusion matrix for validation set, without normalization')
    fig.savefig('Plots/'+tag+'/Confusion_matrix_val.pdf')
    plt.close()

    plt.clf()
    fig = plt.figure()
    plot_confusion_matrix(conf_matrix_val, classes=classtitles, normalize=True, title='Confusion matrix for validation set, normalized')
    fig.savefig('Plots/'+tag+'/Confusion_matrix_val_norm.pdf')
    plt.close()

    plt.clf()
    fig = plt.figure()
    plot_confusion_matrix(conf_matrix_train, classes=classtitles, title='Confusion matrix for training set, without normalization')
    fig.savefig('Plots/'+tag+'/Confusion_matrix_train.pdf')
    plt.close()

    plt.clf()
    fig = plt.figure()
    plot_confusion_matrix(conf_matrix_train, classes=classtitles, normalize=True, title='Confusion matrix for training set, normalized')
    fig.savefig('Plots/'+tag+'/Confusion_matrix_train_norm.pdf')
    plt.close()


def plot_outputs_2d(parameters, pred_vals, lumiweights_vals, colorstr, rootcolors):
    print 'Starting to plot 2d plots of output variables'
    tag = dict_to_str(parameters)
    equallyweighted = parameters['equallyweighted']
    classes = parameters['sampleclasses']
    classtitles = get_classtitles(parameters)
    gErrorIgnoreLevel = kWarning

    gROOT.SetBatch(True);
    for i in classes.keys():
        for j in classes.keys():
            if j <= i: continue
            idx = 0
            hists = []
            for trueclass in classes.keys():
                c1 = TCanvas('c1', 'c1', 600, 600)
                hist = TH2F( classtitles[trueclass], classtitles[trueclass], 100, 0, 1.0001, 100, 0, 1.0001)
                for k in range(pred_vals[trueclass][i].shape[0]):
                    hist.Fill(pred_vals[trueclass][i][k], pred_vals[trueclass][j][k], lumiweights_vals[trueclass][i][k])
                hist.SetMarkerColor(rootcolors[colorstr[trueclass]])
                hist.GetXaxis().SetTitle('Classifier output, node ' + classtitles[i])
                hist.GetYaxis().SetTitle('Classifier output, node ' + classtitles[j])
                hist.Scale(1./hist.Integral())
                hist.GetZaxis().SetRangeUser(1.E-7, 1)
                hist.Draw("COLZ")
                idx += 1
                gStyle.SetOptStat(0)
                c1.SetLogz(True)
                c1.SaveAs('Plots/'+tag+'/Outputs_trueclass'+classtitles[trueclass]+'_node'+str(i)+'_node'+str(j)+'.pdf')
                del c1


def plot_outputs_1d(parameters, colorstr, pred_trains, labels_train, weights_trains, lumiweights_trains, normweights_trains, pred_vals, labels_val, weights_vals, lumiweights_vals, normweights_vals):

    print 'Starting to plot the classifier output distribution'
    tag = dict_to_str(parameters)
    classtitles = get_classtitles(parameters)

    for cl in range(labels_train.shape[1]):
        nbins = 100
        binwidth = 1./float(nbins)
        y_trains = {}
        y_vals = {}
        y_trains_norm = {}
        y_vals_norm = {}
        bin_edges_trains = {}
        bin_edges_vals = {}
        bin_centers = {}
        yerrs = {}
        yerrs_norm = {}

        for i in range(labels_train.shape[1]):
            y_trains[i], dummy = np.histogram(pred_trains[cl][i], bins=nbins, weights=lumiweights_trains[cl][i])
            y_trains_norm[i], bin_edges_trains[i] = np.histogram(pred_trains[cl][i], bins=nbins, weights=weights_trains[cl][i])
            y_vals[i], dummy = np.histogram(pred_vals[cl][i], bins=nbins, weights=lumiweights_vals[cl][i])
            y_vals_norm[i], bin_edges_vals[i] = np.histogram(pred_vals[cl][i], bins=nbins, weights=weights_vals[cl][i])
            bin_centers[i] = 0.5*(bin_edges_trains[i][1:] + bin_edges_trains[i][:-1])
            yerrs_norm[i] = y_vals_norm[i]**0.5
            yerrs[i] = y_vals[i]**0.5
            y_vals_norm[i] = y_vals_norm[i] * normweights_vals[cl][i][0]
            yerrs_norm[i] = yerrs_norm[i] * normweights_vals[cl][i][0]

        plt.clf()
        fig = plt.figure()
        classtitle_to_use = ''
        for i in range(labels_train.shape[1]):
            plt.hist(pred_trains[cl][i], weights=weights_trains[cl][i]*normweights_trains[cl][i], bins=nbins, histtype='step', label='Training sample, ' + classtitles[i], color=colorstr[i])
            plt.errorbar(bin_centers[i], y_vals_norm[i], yerr=yerrs_norm[i], fmt = '.', drawstyle = 'steps-mid-', label='Validation sample, ' + classtitles[i], color=colorstr[i])
            if i == cl:
                classtitle_to_use = classtitles[i]

        plt.legend(loc='best', prop={'size': 8})
        plt.yscale('log')
        plt.xlabel('Classifier output for '+classtitle_to_use)
        plt.ylabel('Normalized number of events / bin')
        fig.savefig('Plots/'+tag+'/Distribution_class'+str(cl)+'_full_norm.pdf')

        plt.clf()
        fig = plt.figure()
        classtitle_to_use = ''
        for i in range(labels_train.shape[1]):
            plt.errorbar(bin_centers[i], y_vals[i], yerr=yerrs[i], fmt = '.', drawstyle = 'steps-mid-', label='Validation sample, ' + classtitles[i], color=colorstr[i])
            if i == cl:
                classtitle_to_use = classtitles[i]

        plt.legend(loc='best', prop={'size': 8})
        plt.yscale('log')
        plt.xlabel('Classifier output for '+classtitle_to_use)
        plt.ylabel('Number of events / bin (weighted by luminosity)')
        fig.savefig('Plots/'+tag+'/Distribution_class'+str(cl)+'_full.pdf')
        plt.close()