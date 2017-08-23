#pylint: disable=C,R,E1101
'''
Based on b9

+ SNN
'''
import torch
import torch.nn as nn
import math
from util_cnn.model import Model
from util_cnn.weightnorm import WeightNorm
import logging
import numpy as np

logger = logging.getLogger("trainer")

class CNN(nn.Module):
    def __init__(self, number_of_classes):
        super(CNN, self).__init__()

        self.features = [
            1, # 64
            6 + 4 * 3 + 2 * 5 + 1 * 7, # =35 # 33
            6 + 4 * 3 + 2 * 5 + 1 * 7, # 17
            6 + 4 * 3 + 2 * 5 + 1 * 7, # 9
            6 + 4 * 3 + 2 * 5 + 1 * 7, # 5
            number_of_classes]

        for i in range(len(self.features) - 1):
            weights = torch.nn.Parameter(torch.FloatTensor(self.features[i+1], self.features[i], 4, 4, 4))
            weights.data.normal_(0, 1 / math.sqrt(self.features[i] * 4 * 4 * 4))
            setattr(self, 'weights{}'.format(i), weights)

            wn = WeightNorm(self.features[i+1])
            setattr(self, "wn{}".format(i), wn)

            bias = torch.nn.Parameter(torch.zeros(1, self.features[i+1], 1, 1, 1))
            setattr(self, 'bias{}'.format(i), bias)

        self.bn_in = nn.BatchNorm3d(1, affine=True)
        self.bn_out = nn.BatchNorm1d(number_of_classes, affine=True)

    def forward(self, x):
        '''
        :param x: [batch, features, x, y, z]
        '''
        x = self.bn_in(x.contiguous())

        for i in range(len(self.features) - 1):
            x = torch.nn.functional.conv3d(x, getattr(self, 'weights{}'.format(i)), stride=2, padding=2)
            x = getattr(self, "wn{}".format(i))(x)
            x = x + getattr(self, 'bias{}'.format(i))

            if i < len(self.features) - 2:
                x = torch.nn.functional.selu(x)

        logger.info(" " * 45 + "%.3f", x.data.std())

        x = x.mean(-1).mean(-1).mean(-1) # [batch, features]
        x = self.bn_out(x.contiguous())

        return x

class MyModel(Model):
    def __init__(self):
        super(MyModel, self).__init__()
        self.cnn = None

    def initialize(self, number_of_classes):
        self.cnn = CNN(number_of_classes)

    def get_cnn(self):
        if self.cnn is None:
            raise ValueError("Need to call initialize first")
        return self.cnn

    def get_batch_size(self, epoch=None):
        return 16

    def get_learning_rate(self, epoch):
        WeightNorm.set_all_momentum(self.cnn, 0.1 if epoch < 5 else 0)
        return 0 if epoch < 5 else 1e-3

    def load_train_files(self, files):
        import glob, random
        files = [random.choice(glob.glob(f + "/*.npz")) for f in files]

        images = np.array([np.load(file)['arr_0'] for file in files], dtype=np.float32)
        images = images.reshape((-1, 1, 64, 64, 64))
        images = torch.FloatTensor(images)
        return images

    def load_eval_files(self, files):
        images = np.array([np.load(file) for file in files], dtype=np.float32)
        images = images.reshape((-1, 1, 64, 64, 64))
        images = torch.FloatTensor(images)
        return images