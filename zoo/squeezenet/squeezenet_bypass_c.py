# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# SqueezeNet v1.0 with simple bypass/composable (2016)
# Paper: https://arxiv.org/pdf/1602.07360.pdf

import tensorflow as tf
from tensorflow.keras import Input, Model
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Concatenate, Add, Dropout
from tensorflow.keras.layers import GlobalAveragePooling2D, Activation

class SqueezeNetBypass(object):
    ''' Construct a SqueezeNet Bypass Convolution Neural Network '''
    # Meta-parameter: number of blocks and filters per group
    # Fire blocks with simple bypass on blocks 2, 4, 6 and 8 
    groups = [ [ { 'n_filters' : 16, 'bypass': False }, 
                 { 'n_filters' : 16, 'bypass': True }, 
                 { 'n_filters' : 32, 'bypass': False } ],
               [ { 'n_filters' : 32, 'bypass': True }, 
                 { 'n_filters' : 48, 'bypass': False }, 
                 { 'n_filters' : 48, 'bypass': True },  
                 { 'n_filters' : 64, 'bypass': False } ],
               [ { 'n_filters' : 64, 'bypass': True } ] ]
    init_weights = 'glorot_uniform'
    _model = None

    def __init__(self, groups=None, dropout=0.5, input_shape=(224, 224, 3), n_classes=1000):
        ''' Construct a SqueezeNet Bypass Convolution Neural Network
            dropout : percentage of dropout
            input_shape: input shape to model
            n_classes  : number of output classes
        '''
        if groups is None:
            groups = SqueezeNetBypass.groups

        # The input shape
        inputs = Input((224, 224, 3))

        # The Stem Group
        x = self.stem(inputs)

        # The Learner
        x = self.learner(x, groups=groups, dropout=dropout)

        # The Classifier
        outputs = self.classifier(x, n_classes)

        self._model = Model(inputs, outputs)

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, _model):
        self._model = _model

    def stem(self, inputs):
        ''' Construct the Stem Group
            inputs : input to the stem
        '''
        x = Conv2D(96, (7, 7), strides=2, padding='same', activation='relu',
               kernel_initializer=self.init_weights)(inputs)
        x = MaxPooling2D(3, strides=2)(x)
        return x

    def learner(self, x, **metaparameters):
        ''' Construct the Learner
            x      : input to the learner
            groups : blocks/filters/bypass per group
            dropout: percent of droput
        '''
        groups  = metaparameters['groups']
        if 'dropout' in metaparameters:
            dropout = metaparameters['dropout']
        else:
            dropout = SqueezeNetBypass.dropout

        last = groups.pop()

        # Add Fire groups, progressively increase number of filters
        for group in groups:
            x = SqueezeNetBypass.group(x, blocks=group)

        # Last fire block
        x = SqueezeNetBypass.fire_block(x, **last[0])

        # Dropout is delayed to end of fire groups
        x = Dropout(dropout)(x)
        return x

    @staticmethod
    def group(x, init_weights=None, **metaparameters):
        ''' Construct the Fire Group
            x       : input to the group
            blocks  : nuumber of filters/bypass per block in group
        '''
        blocks = metaparameters['blocks']

        if init_weights is None:
            init_weights = SqueezeNetBypass.init_weights
            
        for block in blocks:
            x = SqueezeNetBypass.fire_block(x, init_weights=init_weights, **block)

        # Delayed downsampling
        x = MaxPooling2D((3, 3), strides=2)(x)
        return x

    @staticmethod
    def fire_block(x, init_weights=None, **metaparameters):
        ''' Construct a Fire Block
            x        : input to the block
            n_filters: number of filters in the block
            bypass   : whether block has an identity shortcut
        '''
        n_filters = metaparameters['n_filters']
        bypass    = metaparameters['bypass']

        if init_weights is None:
            init_weights = SqueezeNetBypass.init_weights
            
        # remember the input
        shortcut = x

        # squeeze layer
        squeeze = Conv2D(n_filters, (1, 1), strides=1, activation='relu',
                         padding='same', kernel_initializer=init_weights)(x)

        # branch the squeeze layer into a 1x1 and 3x3 convolution and double the number
        # of filters
        expand1x1 = Conv2D(n_filters * 4, (1, 1), strides=1, activation='relu',
                           padding='same', kernel_initializer=init_weights)(squeeze)
        expand3x3 = Conv2D(n_filters * 4, (3, 3), strides=1, activation='relu',
                           padding='same', kernel_initializer=init_weights)(squeeze)

        # concatenate the feature maps from the 1x1 and 3x3 branches
        x = Concatenate()([expand1x1, expand3x3])
    
        # if identity link, add (matrix addition) input filters to output filters
        if bypass:
            x = Add()([x, shortcut])
        
        return x

    def classifier(self, x, n_classes):
        ''' Construct the Classifier '''
        # set the number of filters equal to number of classes
        x = Conv2D(n_classes, (1, 1), strides=1, activation='relu', padding='same',
                   kernel_initializer=self.init_weights)(x)
        # reduce each filter (class) to a single value
        x = GlobalAveragePooling2D()(x)
        x = Activation('softmax')(x)
        return x

# Example
# squeezenet = SqueezeNetBypass()
