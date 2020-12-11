#!/usr/bin/env python
# PandoraBDT.py

from sklearn.ensemble import AdaBoostClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.tree import _tree
from sklearn import preprocessing
from datetime import datetime

import numpy as np
import scipy.stats as sci
import sys
import time
import pickle
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import pandas as pd
import seaborn as sns
import math

from PandoraMVA import *

def DrawVariables(X, Y, labels, logY=True, class_names=['Signal', 'Background']):
    plot_colors = ['b', 'r']
    plot_step = 1.0
    signal_definition = [1, 0]

    num_rows, num_cols = X.shape
    for feature in range(0, num_cols):
        plot_range = (np.quantile(X[:,feature], 0.01), np.quantile(X[:,feature], 0.99))

        # print (len(X[:,feature]), plot_range, Y)
        for i, n, g in zip(signal_definition, class_names, plot_colors):
            # print (len(X[:,feature]), Y[0]==0)
            # print (len(X[:,feature][Y==0]))
            # print (len(X[:,feature][Y==1]))
            entries, bins, patches = plt.hist(X[:,feature][Y == i],
                    bins=50,
                    range=plot_range,
                    facecolor=g,
                    label=n,
                    alpha=.5,
                    edgecolor='k',
                    density=True)
            if (logY):
                plt.yscale('log')
        x1, x2, y1, y2 = plt.axis()
        plt.axis((x1, x2, y1, y2 * 1.1))
        plt.legend()
        plt.ylabel('Entries')
        plt.xlabel(labels[feature])

        plt.tight_layout()
        plotName = 'Feature_' + labels[feature] + '.pdf'
        plt.savefig(plotName)
        plt.show()
        plt.close()

#--------------------------------------------------------------------------------------------------

def Correlation(X, Y):
    signal = []
    background = []

    for idx, x in enumerate(X):
        if Y[idx] == 1:
            signal.append(x)
        elif Y[idx] == 0:
            background.append(x)

    sig = pd.DataFrame(data=signal)
    bkg = pd.DataFrame(data=background)

    # Compute the correlation matrix
    corrSig = sig.corr()
    corrBkg = bkg.corr()

    # Generate a mask for the upper triangle
    mask = np.zeros_like(corrSig, dtype=np.bool)
    mask[np.triu_indices_from(mask)] = True

    jet = plt.get_cmap('jet')

    # Signal Plot
    f, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(corrSig, mask=mask, cmap=jet, vmax=1.0, vmin=-1.0, center=0,
            square=True, linewidths=.5, cbar_kws={"shrink": .5})

    plotName = 'CorrelationMatrixSignal.pdf'
    plt.savefig(plotName)
    plt.show()
    plt.close()

    # Background Plot
    f, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(corrBkg, mask=mask, cmap=jet, vmax=1.0, vmin=-1.0, center=0,
            square=True, linewidths=.5, cbar_kws={"shrink": .5})

    plotName = 'CorrelationMatrixBackground.pdf'
    plt.savefig(plotName)
    plt.show()
    plt.close()

#--------------------------------------------------------------------------------------------------

def TrainAdaBoostClassifer(X_train, Y_train, n_estimatorsValue=3, max_depthValue=2, learning_rateValue=1.0,
        algorithmValue='SAMME', random_stateValue=42):
    # Load the BDT object
    bdtModel = AdaBoostClassifier(DecisionTreeClassifier(max_depth=max_depthValue),
            n_estimators=n_estimatorsValue, learning_rate=learning_rateValue,
            algorithm=algorithmValue, random_state=random_stateValue)

    # Train the model
    startTime = time.time()
    bdtModel.fit(X_train, Y_train)
    endTime = time.time()

    return bdtModel, endTime - startTime

#--------------------------------------------------------------------------------------------------

def WriteXmlFile(filePath, adaBoostClassifer, BDTName):
    datetimeString = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
    with open(filePath, "a") as modelFile:
        indentation = 0
        indentation = OpenXmlTag(modelFile,    'AdaBoostDecisionTree', indentation)
        WriteXmlFeature(modelFile, BDTName, 'Name', indentation)
        WriteXmlFeature(modelFile, datetimeString, 'Timestamp', indentation)

        for idx, estimator in enumerate(adaBoostClassifer.estimators_):
            boostWeight = adaBoostClassifer.estimator_weights_[idx]
            WriteDecisionTree(estimator, modelFile, indentation, idx, boostWeight)

        CloseXmlTag(modelFile,                 'AdaBoostDecisionTree', indentation)

#--------------------------------------------------------------------------------------------------

def Recurse(node, parentnode, depth, position, indentation, decisionTree, modelFile):
    indentation = OpenXmlTag(modelFile, 'Node', indentation)
    WriteXmlFeature(modelFile, node, 'NodeId', indentation)
    WriteXmlFeature(modelFile, parentnode, 'ParentNodeId', indentation)

    if decisionTree.feature[node] != _tree.TREE_UNDEFINED:
        name = decisionTree.feature[node] #(int)(node) #feature_name[node]
        threshold = decisionTree.threshold[node]
        WriteXmlFeature(modelFile, name, 'VariableId', indentation)
        WriteXmlFeature(modelFile, threshold, 'Threshold', indentation)
        WriteXmlFeature(modelFile, decisionTree.children_left[node], 'LeftChildNodeId', indentation)
        WriteXmlFeature(modelFile, decisionTree.children_right[node], 'RightChildNodeId', indentation)
        indentation = CloseXmlTag(modelFile, 'Node', indentation)
        indentation = indentation + 4
        Recurse(decisionTree.children_left[node], node, depth + 1, 'Left', indentation, decisionTree, modelFile)
        Recurse(decisionTree.children_right[node], node, depth + 1, 'Right', indentation, decisionTree, modelFile)
        indentation = indentation - 4
    else:
        result = decisionTree.value[node]
        if (result.tolist()[0][1] > result.tolist()[0][0]):
            WriteXmlFeature(modelFile, 'true', 'Outcome', indentation)
        else:
            WriteXmlFeature(modelFile, 'false', 'Outcome', indentation)

        indentation = CloseXmlTag(modelFile, 'Node', indentation)

#--------------------------------------------------------------------------------------------------

def WriteDecisionTree(estimator, modelFile, indentation, treeIdx, boostWeight):
    decisionTree = estimator.tree_
    indentation = OpenXmlTag(modelFile, 'DecisionTree', indentation)

    WriteXmlFeature(modelFile, treeIdx, 'TreeIndex', indentation)
    WriteXmlFeature(modelFile, boostWeight, 'TreeWeight', indentation)
    Recurse(0, -1, 1, 'Start', indentation, decisionTree, modelFile)

    indentation = CloseXmlTag(modelFile, 'DecisionTree', indentation)

#--------------------------------------------------------------------------------------------------

def SerializeToPkl(fileName, model):
    with open(fileName, 'wb') as f:
        pickle.dump(model, f)

#--------------------------------------------------------------------------------------------------

def LoadFromPkl(fileName):
    with open(fileName, 'rb') as f:
        model = pickle.load(f)

        return model

#--------------------------------------------------------------------------------------------------

def FindOptimalSignificanceCut(bdtModel, X_train, Y_train, parameters):
    # Find optimal cut based on significance
    train_results = bdtModel.decision_function(X_train)
    fig, ax = plt.subplots()

    sigEff = 0
    bkgRej = 0
    sigEntries = []
    bkgEntries = []

    for i, n, g in zip(parameters['SignalDefinition'], parameters['ClassNames'], parameters['PlotColors']):
        entries, bins, patches = ax.hist(train_results[Y_train == i],
                bins = parameters['nBins'],
                range = (-1,1),
                facecolor = g,
                label = 'Class %s' % n,
                alpha = .5,
                edgecolor = 'k')
        if i == 1:
            sigEntries = entries
        elif i == 0:
            bkgEntries = entries


    nSigEntries = sum(sigEntries)
    nBkgEntries = sum(bkgEntries)
    optimalSignif = 0
    optimalSigEff = 0
    optimalBkgRej = 0
    optimalBinCut = 0
    optimalScoreCut = 0

    for binCut in range(0, parameters['nBins']):
        nSigPassing = sum(sigEntries[binCut:])
        nBkgPassing = sum(bkgEntries[binCut:])

        signif = 0
        if (nSigPassing + nBkgPassing > 0):
            signif = nSigPassing / math.sqrt(nSigPassing + nBkgPassing)

        if (signif > optimalSignif):
            nBkgFailing = sum(bkgEntries[:binCut])
            sigEff = 100 * nSigPassing / nSigEntries
            bkgRej = 100 * nBkgFailing / nBkgEntries
            optimalSignif = signif
            optimalBinCut = binCut
            optimalScoreCut = bins[optimalBinCut]
            optimalSigEff = sigEff
            optimalBkgRej = bkgRej

#    print('Optimal signif : ' + str(optimalSignif))
#    print('Optimal sigEff : ' + str(optimalSigEff))
#    print('Optimal bkgRej : ' + str(optimalBkgRej))
#    print('Optimal binCut : ' + str(optimalBinCut))
#    print('Optimal scoreCut : ' + str(round(optimalScoreCut,2)))
    parameters['OptimalBinCut'] = optimalBinCut
    parameters['OptimalScoreCut'] = optimalScoreCut
    plt.close()

#--------------------------------------------------------------------------------------------------

def PlotBdtScores(bdtModel, X_test, Y_test, X_train, Y_train, title, parameters):
    # Testing BDT Using Remainder of Training Sample
    test_results = bdtModel.decision_function(X_test)
    train_results = bdtModel.decision_function(X_train)

    minRange = min(min(test_results),min(train_results))
    maxRange = max(max(test_results),max(train_results))

    test_results_signal = test_results[Y_test==1]
    train_results_signal = train_results[Y_train==1]
    test_results_background = test_results[Y_test==0]
    train_results_background = train_results[Y_train==0]

    fig, ax = plt.subplots()

    ax.set_title(title)

    sigEff = 0
    bkgRej = 0

    for i, n, g in zip(parameters['SignalDefinition'], parameters['ClassNames'], parameters['PlotColors']):
        entries, bins, patches = ax.hist(test_results[Y_test == i],
                bins = parameters['nBins'],
                range = (-1,1),
                facecolor = g,
                label='%s' % n,
                alpha=.5,
                density=True,
                edgecolor='k')

        counts,bin_edges = np.histogram(train_results[Y_train == i],
                range = (-1,1), bins = parameters['nBins'], density=True)

        bin_centres = (bin_edges[:-1] + bin_edges[1:])/2.
        ax.errorbar(bin_centres, counts, fmt='o', color=g)

        if i == 1:
            nEntries = sum(entries)
            nEntriesPassing = sum(entries[parameters['OptimalBinCut']:])
            sigEff = nEntriesPassing/nEntries
        elif i == 0:
            nEntries = sum(entries)
            nEntriesFailing = sum(entries[:parameters['OptimalBinCut']])
            bkgRej = nEntriesFailing/nEntries

    signalKSTest, ksSig = sci.ks_2samp(test_results_signal, train_results_signal)
    backgroundKSTest, ksBck = sci.ks_2samp(test_results_background, train_results_background)

    plt.text(0.75, 0.75, "Sig Eff {:.4%}, \nBkg Rej {:.4%}, \nScore Cut {:.2},\n Signal P value {:.2}, \n Background P value {:.2} "
            .format(sigEff,bkgRej,parameters['OptimalScoreCut'], ksSig, ksBck),
            horizontalalignment='center',
            verticalalignment='center',
            transform = ax.transAxes)

    x1, x2, y1, y2 = plt.axis()
    plt.axis((x1, x2, y1, y2 * 1.1))
    plt.legend(loc='upper right')
    plt.ylabel('Samples')
    plt.xlabel('Score')
    plt.tight_layout()
    plt.savefig(title + '_NTrees_' + str(parameters['nTrees']) + '_TreeDepth_' + str(parameters['TreeDepth']) + '.png')
    plt.show()
    plt.close()

    print("Signal Efficiencey: "+str(sigEff)+" and background rejection: "+str(bkgRej))
    print("KS Signal:     "+str(signalKSTest)+" with P value: "+str(ksSig))
    print("KS BackGround: "+str(backgroundKSTest)+" with P value: "+str(ksBck))
    return ksSig, ksBck
