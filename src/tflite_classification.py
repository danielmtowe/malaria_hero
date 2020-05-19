#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep 18 2018

@author: carlos atico ariza
"""
import os
import re
import tensorflow as tf
import tflite_runtime.interpreter as tflite
import numpy as np
import pandas as pd
import sys
import gc


def tflite_img_class(image_dir=[], prediction_csv='malaria.csv',
                     trained_model='../models/model.tflite',
                     ):
    '''This function classifies if a cell is infected with the Malaria parasite
    using Tensor Flow lite

    Arguments
    image_dir:      A directory containing .png images; one cell per image
    prediction_csv: csv file where predictions for each image is saved
    trained_model:  the trained TFLite model modified to detect parasites in
                    single cells
    '''
    IMAGE_SIZE = 112

    if image_dir:
        print("Please select a directory housing .png images of single cell.")

    print(image_dir)
    path, dirs, files = next(os.walk("/usr/lib"))
    file_count = len(files)

    # run all in one batch: make batch size = file counts
    image_generator = tf.keras.preprocessing.image.ImageDataGenerator(
        rescale=1. / 255)

    # creates a generator that modifies images to 112x112 pixels
    unclassified_img_gen = (image_generator.flow_from_directory(
                            image_dir,
                            target_size=(
                                IMAGE_SIZE,
                                IMAGE_SIZE),
                            batch_size=file_count,
                            shuffle=False))

    # Load TFLite model and allocate tensors.
    interpreter = tflite.Interpreter(model_path=trained_model)
    interpreter.allocate_tensors()

    # Get input and output tensors.
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    image_batch, image_name = next(unclassified_img_gen)

    predictions = []
    for image in image_batch:
        interpreter.set_tensor(input_details[0]['index'], [image])
        interpreter.invoke()

        output_data = interpreter.get_tensor(output_details[0]['index'])
        predictions.append(output_data[0])

    predictions = np.vstack(predictions)
    positive_prob = predictions[:, 0]
    classifications = np.argmax(predictions, 1)

    files_processed = pd.DataFrame({'fn': unclassified_img_gen.filenames,
                                    'Predicted_label': classifications,
                                    'Parasitized_probability': positive_prob,
                                    })

    # example file name: folder\C33P1thinF_IMG_20150619_114756a_cell_181.png,
    def split_it(row):
        c = re.findall(r'C(\d{1,3})', row['fn'])
        patient = re.findall(r'P(\d{1,3})', row['fn'])
        cell_no = re.findall(r'cell_(\d{1,3})', row['fn'])
        for i, x in enumerate([c, patient, cell_no]):
            if x:
                if i == 0:
                    row['Slide'] = c[0]
                if i == 1:
                    row['Patient'] = patient[0]
                if i == 2:
                    row['Cell'] = cell_no[0]
        return row

    files_processed = files_processed.apply(split_it, axis=1)
    print(files_processed.head())
    files_processed.to_csv(f'../results/predicted_{prediction_csv}')

    # Groupping by Patient to give a better product application
    summary = pd.DataFrame()
    summary['Total Cells Examined'] = (files_processed.groupby(['Patient'])
                                       ['Predicted_label'].count())
    summary[u'% Infected Cells'] = (files_processed.groupby('Patient')
                                    ['Predicted_label'].sum()
                                    / summary['Total Cells Examined'])

    summary.sort_values(by='% Infected Cells', ascending=False, inplace=True)
    # Format to two decimal places
    summary['% Infected Cells'] = summary['% Infected Cells'].map(
                                          '{:,.1f}'.format).astype(float)
    summary.to_csv('../results/summary.csv')
    print(summary.head())
    # collect garbage
    del files_processed
    gc.collect()

    return summary


if __name__ == '__main__':
    tflite_img_class(image_dir=sys.argv[1], prediction_csv=sys.argv[2],
                     trained_model=sys.argv[3])

# For testing the script on command line:
# python ../datasets/cell_images test_predictions.csv
# ../models/trained_RF.sav