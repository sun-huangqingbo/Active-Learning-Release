import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import math
import multiprocessing
import csv
import scipy
import argparse

parser = argparse.ArgumentParser(description='Active learning on the synthetic data')
parser.add_argument('-unique', type=float, default=0.4, help='uniqueness of the synthetic data (default: 0.4)')
parser.add_argument('-responsive', type=float, default=0.8, help='responsiveness of the synthetic data (default: 0.8)')
parser.add_argument('-random', action='store_true', help='whether run the simulation using the randon learner')
parser.add_argument('-adjustment', action='store_false', help='confidence adjustment setting. Default True, if not specified. If specified, set it to false.')
parser.add_argument('-phenotype', type=int, default=32,  help='number of the phenotypes')
parser.add_argument('-strategy', type=str, default='hybrid', help='query strategy for the active learner')
args = parser.parse_args()

def Read_in_csv(filename):
    csv_file=open(filename)     
    csv_reader_lines = csv.reader(csv_file)    
    date_PyList=[]  
    for one_line in csv_reader_lines:  
        date_PyList.append(one_line)    
    date_ndarray = np.array(date_PyList)
    print(date_ndarray)

def AddNoise(data, percent):
    added = []
    noise_num = int(len(data) * len(data[0]) * percent)
    i = 0
    while i < noise_num:
        row = np.random.randint(0, 99)
        col = np.random.randint(0, 99)
        while (row, col) in added:
            row = np.random.randint(0, 99)
            col = np.random.randint(0, 99)
        noise_index = np.random.randint(0, 8)
        while data[row][col] == str(noise_index):
            noise_index = np.random.randint(0, 8)
        data[row][col] = str(noise_index)
        added.append((row, col))
        i += 1
    return data


def Preparing_Labels(labelnums):
    labels = []
    for i in range(0, labelnums):
        labels.append(i)
    return labels

def Generate_binary_result(prob):
    rand = np.random.uniform()
    if rand < prob:
        return True
    else: return False

def CountKnownNum(currdata):
    count = 0
    for row in currdata:
        for e in row:
            if e != -1:
                count+=1
    return count

def Make_Selections_score(num, predictions):
    batch = []
    for prediction in predictions:
        if len(batch) < num:
            batch.append(prediction)  #prediction format (row, col, label, score)
        else:
            min_score = batch[0][3]
            index = 0
            for i in range(len(batch)):
                if batch[i][3] < min_score:
                    min_score = batch[i][3]
                    index = i
            if prediction[3] > min_score:
                batch.remove(batch[index])
                batch.append(prediction)
    return batch

def Make_Selections_score2(num, predictions):
    batch = []
    for prediction in predictions:
        if len(batch) < num:
            batch.append(prediction)  #prediction format (row, col, label, score)
        else:
            max_score = batch[0][3]
            index = 0
            for i in range(len(batch)):
                if batch[i][3] > max_score:
                    max_score = batch[i][3]
                    index = i
            if prediction[3] < max_score:
                batch.remove(batch[index])
                batch.append(prediction)
    return batch





def Generating_Truth(num, uniqueness, responsiveness, numtypes):
    labels = Preparing_Labels(numtypes)
    table = []
    unique_num = int(num * uniqueness)
    for i in range(unique_num):
        row = []
        rand = np.random.randint(len(labels))
        row.append(labels[rand])
        table.append(row)
    for i in range(unique_num):
        rest_pool = labels.copy()
        rest_pool.remove(table[i][0])
        for j in range(unique_num - 1):
            if Generate_binary_result(responsiveness):
                table[i].append(rest_pool[np.random.randint(len(rest_pool))])
            else:
                table[i].append(table[i][0])
    for j in range(num - unique_num):
        rand = np.random.randint(unique_num)
        for i in range(unique_num):
            table[i].append(table[i][rand])
    for i in range(num - unique_num):
        table.append(table[np.random.randint(unique_num)])
    table = np.array(table)
    #table = cp.array(table)
    filename = str(uniqueness) + 'test_data.csv'
    pd_data = pd.DataFrame(table)
    pd_data.to_csv('test_data.csv',index=False,header=False)
    return table


def Initialize_Data(ground_truth):
    currdata = []
    for i in range(0, len(ground_truth) * len(ground_truth[0])):
        currdata.append(-1)
    currdata = np.array(currdata).reshape(len(ground_truth), len(ground_truth[0])) 
    for i in range(len(ground_truth)):
        label = ground_truth[i][i]
        currdata[i][i] = label

    return currdata


    
        
def Find_remain_col(row, col, threshold, currdata):
    result = {}
    cols = []
    for i in range(len(currdata[0])):
        cols.append(i)
    cols.remove(col)
    for col2 in cols:
        if currdata[row][col2] != -1:
            score = Count_Col_Score(col, col2, currdata)
            result[col2] = score

    batchsize = max(threshold, 1)
    maxcols = []
    for key in result:
        if len(maxcols) < batchsize - 1:
            maxcols.append(key)
        elif len(maxcols) == batchsize - 1:
            maxcols.append(key)
            mincol = maxcols[0]
            for col_ in maxcols:
                if result[col_] < result[mincol]:
                    mincol = col_
        else:
            if result[key] > result[mincol]:
                maxcols.remove(mincol)
                maxcols.append(key)
                mincol = maxcols[0]
                for col_ in maxcols:
                    if result[col_] < result[mincol]:
                        mincol = col_

    return maxcols




def Predict_One_Col(col, currdata, step, panelty):
    n_conflicts = 0
    predictions = []
    #index is consistent with currdata
    unknown_rows = []


    for row in range(len(currdata)):
        if currdata[row][col] == -1:
            unknown_rows.append(row)

    while True:
        if len(unknown_rows) == 0 or n_conflicts > len(currdata):
            break
        predicted = []
        community = Find_Cols_With_n_Conflicts(n_conflicts + step, n_conflicts, currdata, col)
        if len(community) != 0:
            for urow in unknown_rows:
                prediction = {}
                count = {}
                for col2 in community:
                    if currdata[urow][col2] != -1:
                        label = currdata[urow][col2]
                        if label in prediction:
                            prediction[label] += Count_Col_Score(col, col2, panelty, currdata)
                            count[label] += 1
                        else:
                            prediction[label] = Count_Col_Score(col, col2, panelty, currdata)
                            count[label] = 1
                
                for label in prediction:
                    prediction[label] = prediction[label]/count[label]
                

                if len(prediction) != 0:
                    predictions.append((urow, col, prediction))
                    predicted.append(urow)
            n_conflicts += step
            for row in predicted:
                unknown_rows.remove(row)
    
        else:
            n_conflicts += step

        
    return predictions

def Count_Row_Score(row, currdata):
    count = 0
    for col in range(len(currdata[0])):
        if currdata[row][col] != -1:
            count+=1
    return count


def Count_Col_Score(col, col2, panelty, currdata):
    score = 0
    for row in currdata:
        if row[col] != -1 and row[col2] != -1 and row[col] == row[col2]:
            score += 1
        if row[col] != -1 and row[col2] != -1 and row[col] != row[col2]:
            score -= panelty
    return score


def Find_Cols_With_n_Conflicts(upperbound, lowerbound, currdata, col):
    #row is index of rows in currdata
    result = []
    cols = []
    for i in range(len(currdata[0])):
        cols.append(i)
    cols.remove(col)
    for col2 in cols:
        conflict = 0
        for row in range(len(currdata)):
            if currdata[row][col] != -1 and currdata[row][col2] != -1 and currdata[row][col] != currdata[row][col2]:
                conflict += 1
        if conflict <  upperbound and conflict >= lowerbound:
            result.append(col2)

    return result



def Split_Parameters(pl):
    col = pl[0]
    currdata = pl[1]
    step = pl[2]
    panelty = pl[3]
    return Predict_One_Col(col, currdata, step, panelty)


def Simulate_Once(currdata, step, panelty):
    prediction_from_col = []
    prediction_from_row = []
    predictions = {}
    parameters = []
    for col in range(len(currdata[0])):
        parameters.append((col, currdata, step, panelty))
    

    core_num = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(core_num)
    predictions_col = pool.map(Split_Parameters, parameters)
    pool.close()
    pool.join()
        #p: row, col, dict

    for l in predictions_col:
        for p in l:
            prediction_from_col.append(p)
    for p in prediction_from_col:
        predictions[(p[0], p[1])] = p[2]
    
    
    currdataT = currdata.T
    parameters.clear()
    
    for col_ in range(len(currdataT[0])):
        parameters.append((col_, currdataT, step, panelty))

    core_num = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(core_num)
    predictions_row = pool.map(Split_Parameters, parameters)
    pool.close()
    pool.join()

    for l in predictions_row:
        for p in l:
            prediction_from_row.append(p)

    for p in prediction_from_row:
        if (p[1], p[0]) in predictions:
            for key in p[2]:
                if key in predictions[(p[1], p[0])]:
                    predictions[(p[1], p[0])][key] = p[2][key] + predictions[(p[1], p[0])][key]
                    #predictions[(p[1], p[0])][key] /= 2
                else:
                    predictions[(p[1], p[0])][key] = p[2][key]
        else:
            predictions[(p[1], p[0])][key] = p[2]

    return predictions


def Make_Selections_random(num, predictions):
    batch = []
    batch_index = []
    for i in range(num):
        rand = np.random.randint(len(predictions))
        while rand in batch_index:
            rand = np.random.randint(len(predictions))
        batch_index.append(rand)
    for index in batch_index:
        batch.append(predictions[index])
    return batch





def Calculate_Resp(currdata, panelty):
    resps = []
    resps2 = []
    for row in currdata:
        resp = 0
        row_label = {}
        for e in row:
            if e != -1 and e not in row_label:
                row_label[e] = 1
            elif e != -1 and e in row_label:
                row_label[e] += 1
        max_label = ''
        maxscore = -1000000
        for key in row_label:
            if row_label[key] > maxscore:
                maxscore = row_label[key]
                max_label = key
        resp = maxscore
        total = maxscore
        for key in row_label:
            if key != max_label:
                resp -= panelty * row_label[key]
                total += row_label[key]
        resps.append((max_label, resp))
        resps2.append(maxscore/total)
    resps2 = np.array(resps2)
    resp_average = resps2.mean()
    return resps, 1 - resp_average

def Calculate_entropy(prediction):
    entropy = 0
    for key in prediction:
        p = prediction[key]
        entropy -= p * scipy.log2(p)
    return entropy


def Trail(uniqueness, responsiveness, strategy, phenotype_num):
    ground_truth10 = Generating_Truth(100, uniqueness, responsiveness, phenotype_num)
    #ground_truth10 = AddNoise(ground_truth_, 0.1)
    currdata = Initialize_Data(ground_truth10)
    total = len(currdata) * len(currdata[0])
    knownnum = CountKnownNum(currdata)
    P = 2.5
    batch_size = 100
    accus = {}
    accusR = {}
    accusHybrid = {}
    accusEntropy = {}
#----------------------------------------------------------------------
#random
    if args.random:
        print(currdata[1][1] == ground_truth10[1][1])
        currdata = Initialize_Data(ground_truth10)
        total = len(currdata) * len(currdata[0])
        knownnum = CountKnownNum(currdata)
        while knownnum < total:

            step = 1
            panelty =  P * (knownnum/total) 
            prediction_temp = Simulate_Once(currdata, step, panelty)
            

            curr_resp, resp_average = Calculate_Resp(currdata, panelty)

            predictions = []
            count = len(prediction_temp)
            correct = 0
            mistake = []
            corrects = []
            for key in prediction_temp:
                row = key[0]
                col = key[1]
                dictp = prediction_temp[key]
                maxscore = -10000
                maxlabel = ''
                for label in dictp:
                    if dictp[label] > maxscore:
                        maxlabel = label
                        maxscore = dictp[label]
                if args.adjustment:
                    if maxscore < curr_resp[row][1]:
                        maxlabel = curr_resp[row][0]
                
                #score2 = Calculate_TrueFalsth_Sum(prediction_temp[key], maxlabel)
                if ground_truth10[row][col] == maxlabel:
                        correct+=1
                        corrects.append(maxscore)
                else:
                    mistake.append(maxscore)
                #TF_ratio = Calculate_TrueFalsth_Ratio(prediction_temp[key], maxlabel)
                uncertain_score = maxscore
                #postion_score = Calculate_Position_Score2(row, col, currdata)
                predictions.append([row, col, maxlabel, uncertain_score])
            knownnum = CountKnownNum(currdata)

            accu = 1 - (count - correct)/total
            accusR[knownnum] = accu
            size = min(batch_size, total - knownnum)
            #selections = Make_Selections_score(size, predictions)
            selections = Make_Selections_random(size, predictions)

            for selection in selections:
                row = selection[0]
                col = selection[1]
                currdata[row][col] = ground_truth10[row][col]
            knownnum = CountKnownNum(currdata)

#-------------------------------------------------------------------------------------------------------------------------
#active learning
    currdata = Initialize_Data(ground_truth10)
    print(currdata[1][1] == ground_truth10[1][1])
    total = len(currdata) * len(currdata[0])
    knownnum = CountKnownNum(currdata)
    while knownnum < total:
        step = 1
        panelty = P * (knownnum/total)
        prediction_temp = Simulate_Once(currdata, step, panelty)
        curr_resp, resp_average = Calculate_Resp(currdata, panelty)

        predictions = []
        count = len(prediction_temp)
        correct = 0
        mistake = []
        corrects = []
        for key in prediction_temp:
            row = key[0]
            col = key[1]
            dictp = prediction_temp[key]
            maxscore = -10000
            maxlabel = ''
            for label in dictp:
                if dictp[label] > maxscore:
                    maxlabel = label
                    maxscore = dictp[label]
            if args.adjustment:
                if maxscore < curr_resp[row][1]:
                    maxlabel = curr_resp[row][0]
            
            if ground_truth10[row][col] == maxlabel:
                    correct+=1
                    corrects.append(maxscore)
            else:
                mistake.append(maxscore)
            #TF_ratio = Calculate_TrueFalsth_Ratio(prediction_temp[key], maxlabel)
            bias = 1 - min(dictp.values())
            for key in dictp:
                dictp[key] += bias
            k = 1 / sum(dictp.values())
            for key in dictp:
                dictp[key] *= k
            uncertain_score = Calculate_entropy(dictp)
            predictions.append([row, col, maxlabel, maxscore, uncertain_score])
        knownnum = CountKnownNum(currdata)
        if args.adjustment:
            accu = 1 - (count - correct)/total
            accus[knownnum] = accu

        size = min(batch_size, total - knownnum)
        if strategy == 'hybrid':
            selections = Make_Selections_score2(size*0.5, predictions)
            for p in selections:
                predictions.remove(p)
            for p in predictions:
                p[3] = p[4]
            selections2 = Make_Selections_score(size*0.5, predictions)
        elif strategy == 'entropy':
            selections = []
            for p in selections:
                predictions.remove(p)
            for p in predictions:
                p[3] = p[4]
            selections2 = Make_Selections_score(size, predictions)
        elif strategy == 'score':
            selections = Make_Selections_score2(size, predictions)
            selections2 = []
        else: raise ValueError('unknown query strategy.')

        for selection in selections:
            row = selection[0]
            col = selection[1]
            currdata[row][col] = ground_truth10[row][col]
        for selection in selections2:
            row = selection[0]
            col = selection[1]
            currdata[row][col] = ground_truth10[row][col]
        knownnum = CountKnownNum(currdata)
    
    print('uniquesness: ', uniqueness, 'responsiveness: ', responsiveness)
    print(' ')
    print(' ')
    

    plt.plot(list(accus.keys()), list(accus.values()), 'o-', label= args.strategy + 'active learning')
    if args.random:
        plt.plot(list(accus.keys()), list(accusR.values()), 'o-', label = 'random learning')
    plt.legend(loc='best')
    plt.show()
    
    
    
    filename = 'unique-' + str(uniqueness) + 'responsive-' + str(responsiveness) + '.csv'
    result = []
    result.append(accus.keys())
    result.append(accus.values())
    result.append(accusR.values())
    pd_data = pd.DataFrame(result)
    pd_data.to_csv(filename,index=False,header=False)

    
def main():
    print(args.unique, args.responsive, args.strategy, args.phenotype, args.random, args.adjustment)
    Trail(args.unique, args.responsive, args.strategy, args.phenotype)


if __name__ == "__main__":
    main()

