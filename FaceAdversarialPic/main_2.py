#python3
# -*- coding: utf-8 -*-
# File  : main-3.py
# Author: Wang Chao
# Date  : 2019-08-26



import os
import sys
import time
import torch
import cv2
import warnings
import random
import numpy as np
import argparse
from PIL import Image
import scipy.stats as st
from torchvision import models
from torchvision import transforms
import torch.nn as nn
from PIL import Image
import matplotlib.pyplot as plt

import torch.nn.functional as F
from tqdm import *

warnings.filterwarnings('ignore')

import sys

sys.path.append('../')

from res_facenet.models import model_920, model_921
from Face_recognition.inception_resnet_v1.inception_resnet_v1 import InceptionResnetV1
from Face_recognition.irse.model_irse import IR_50, IR_152


def img2tensor(img):
    img = img.swapaxes(1, 2).swapaxes(0, 1)
    img = np.reshape(img, [1, 3, 112, 112])
    img = np.array(img, dtype=np.float32)
    img = (img - 127.5) / 128.0
    img = torch.from_numpy(img)
    return img


def gkern(kernlen=21, nsig=3):
    """Returns a 2D Gaussian kernel array."""
    import scipy.stats as st

    interval = (2 * nsig + 1.) / (kernlen)
    x = np.linspace(-nsig - interval / 2., nsig + interval / 2., kernlen + 1)
    kern1d = np.diff(st.norm.cdf(x))
    kernel_raw = np.sqrt(np.outer(kern1d, kern1d))
    kernel = kernel_raw / kernel_raw.sum()
    return kernel


class GaussianBlur(nn.Module):
    def __init__(self, kernel):
        super(GaussianBlur, self).__init__()
        self.kernel_size = len(kernel)
        # print('kernel size is {0}.'.format(self.kernel_size))
        assert self.kernel_size % 2 == 1, 'kernel size must be odd.'

        self.kernel = torch.FloatTensor(kernel).unsqueeze(0).unsqueeze(0)
        self.weight = nn.Parameter(data=self.kernel, requires_grad=False)

    def forward(self, x):
        x1 = x[:, 0, :, :].unsqueeze_(1)
        x2 = x[:, 1, :, :].unsqueeze_(1)
        x3 = x[:, 2, :, :].unsqueeze_(1)
        padding = self.kernel_size // 2
        x1 = F.conv2d(x1, self.weight, padding=padding)
        x2 = F.conv2d(x2, self.weight, padding=padding)
        x3 = F.conv2d(x3, self.weight, padding=padding)
        x = torch.cat([x1, x2, x3], dim=1)
        return x


class TVLoss(nn.Module):
    def __init__(self, TVLoss_weight=1):
        super(TVLoss, self).__init__()
        self.TVLoss_weight = TVLoss_weight

    def forward(self, x):
        batch_size = x.size()[0]
        h_x = x.size()[2]
        w_x = x.size()[3]
        count_h = self._tensor_size(x[:, :, 1:, :])
        count_w = self._tensor_size(x[:, :, :, 1:])
        h_tv = torch.pow((x[:, :, 1:, :] - x[:, :, :h_x - 1, :]), 2).sum()
        w_tv = torch.pow((x[:, :, :, 1:] - x[:, :, :, :w_x - 1]), 2).sum()
        return self.TVLoss_weight * 2 * (h_tv / count_h + w_tv / count_w) / batch_size

    def _tensor_size(self, t):
        return t.size()[1] * t.size()[2] * t.size()[3]


# def img2tensor_224(x):
#     trfrm = transforms.Compose([
#         lambda x: x.convert('RGB'),
#         transforms.Resize(112),
#         transforms.CenterCrop(112),
#         transforms.ToTensor(),
#         transforms.Normalize(mean=[0.485, 0.456, 0.406],
#                              std=[0.229, 0.224, 0.225])])
#
#     return trfrm(x).unsqueeze(0)


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # model920 = model_920().to(device)
    model920_facenet_criterion = nn.MSELoss()
    # model921 = model_921()
    # model921_facenet_criterion = nn.MSELoss()

    InceptionResnet_model_1 = InceptionResnetV1(pretrained='vggface2').eval().to(device)
    print('load InceptionResnet-vggface2.pt successfully')

    InceptionResnet_model_2 = InceptionResnetV1(pretrained='casia-webface').eval().to(device)
    print('load InceptionResnet-casia-webface.pt successfully')

    IR_50_model_1 = IR_50([112, 112])
    IR_50_model_1.load_state_dict(
        torch.load(
            '/notebooks/Workspace/tmp/pycharm_project_314/TianChi/Face_recognition/irse/model/backbone_ir50_asia.pth'))
    IR_50_model_1.eval().to(device)
    print('load IR_50 successfully')

    IR_152_model_1 = IR_152([112, 112])
    IR_152_model_1.load_state_dict(
        torch.load(
            '/notebooks/Workspace/tmp/pycharm_project_314/TianChi/Face_recognition/irse/model/Backbone_IR_152_Epoch_112_Batch_2547328_Time_2019-07-13-02-59_checkpoint.pth'))
    IR_152_model_1.eval().to(device)
    print('load IR_152 successfully')


    # IR_152_model_2 = IR_152([112, 112])
    # IR_152_model_2.load_state_dict(
    #     torch.load(
    #         '/notebooks/Workspace/tmp/pycharm_project_314/TianChi/Face_recognition/irse/model/Head_ArcFace_Epoch_112_Batch_2547328_Time_2019-07-13-02-59_checkpoint.pth'))
    # IR_152_model_2.eval().to(device)
    # print('load IR_152_ArcFace successfully')

    import insightface

    Insightface_iresent100 = insightface.iresnet100(pretrained=True)
    Insightface_iresent100.eval().to(device)
    print('load Insightface_iresent100 successfully')


    criterion = nn.MSELoss()
    # cpu
    # collect all images to attack
    paths = []
    picpath = '/notebooks/Workspace/tmp/pycharm_project_314/TianChi/images'
    for root, dirs, files in os.walk(picpath):
        for f in files:
            paths.append(os.path.join(root, f))
    random.shuffle(paths)

    # paras
    eps = 1
    steps = 50
    output_path = './output_img'
    momentum = 1.0

    for path in tqdm(paths):

        start = time.time()
        print('processing ' + path + '  ===============>')
        image = Image.open(path)

        # define paras
        # in_tensor is origin tensor of image
        # in_variable changes with gradient

        in_tensor = img2tensor(np.array(image))
        # print(in_tensor.shape)
        in_variable = in_tensor.detach().to(device)
        in_tensor = in_tensor.squeeze().to(device)
        adv = None

        # in_tensor= img2tensor_224(image)
        # # print(in_tensor.shape)
        # in_variable = in_tensor.to(device)
        # in_tensor = in_tensor.squeeze().to(device)
        # adv = None

        #
        # # origin feature
        # origin_model920 = model920(in_variable).to(device)
        # origin_model921 = model921(in_variable)
        origin_InceptionResnet_model_1 = InceptionResnet_model_1(in_variable)
        origin_InceptionResnet_model_2 = InceptionResnet_model_2(in_variable)
        origin_IR_50_model_1 = IR_50_model_1(in_variable)
        origin_IR_152_model_1 = IR_152_model_1(in_variable)
        # origin_IR_152_model_2 = IR_152_model_2(in_variable)
        origin_Insightface_iresent100 = Insightface_iresent100(in_variable)

        # 1. untarget attack -> random noise
        # 2. target attack -> x = alpha * target + (1 - alpha) * x
        perturbation = torch.Tensor(3, 112, 112).uniform_(-0.1, 0.1).to(device)
        in_variable = in_variable + perturbation
        in_variable.data.clamp_(-1.0, 1.0)
        in_variable.requires_grad = True
        g_noise = 0.0

        #  sum gradient
        for i in range(steps):
            # print('step: ' + str(i))
            # in_variable = in_variable.to(device)
            # out_model920 = model920(in_variable)
            # out_model921 = model921(in_variable)
            out_InceptionResnet_model_1 = InceptionResnet_model_1(in_variable)
            out_InceptionResnet_model_2 = InceptionResnet_model_2(in_variable)
            out_IR_50_model_1 = IR_50_model_1(in_variable)
            out_IR_152_model_1 = IR_152_model_1(in_variable)
            # out_IR_152_model_2 = IR_152_model_2(in_variable)
            out_Insightface_iresent100 = Insightface_iresent100(in_variable)


            # loss = criterion(origin_feat_ir50_epoch120, out_feat_ir50_epoch120)
            # loss = criterion(origin_model920, out_model920) + criterion(origin_model921,out_model921) + criterion(
            #     origin_InceptionResnet_model, out_InceptionResnet_model)
            # loss = criterion(origin_InceptionResnet_model_1, out_InceptionResnet_model_1) + \
            #        criterion(origin_InceptionResnet_model_2, out_InceptionResnet_model_2) + \
            #        criterion(origin_IR_50_model_1, out_IR_50_model_1) + \
            #        criterion(origin_IR_152_model_1, out_IR_152_model_1) + \
            #        criterion(origin_IR_152_model_2, out_IR_152_model_2) + \
            #        criterion(origin_Insightface_iresent100, out_Insightface_iresent100)
            loss = criterion(origin_InceptionResnet_model_1, out_InceptionResnet_model_1) + \
                   criterion(origin_InceptionResnet_model_2, out_InceptionResnet_model_2) + \
                   criterion(origin_IR_50_model_1, out_IR_50_model_1) + \
                   criterion(origin_IR_152_model_1, out_IR_152_model_1) + \
                   criterion(origin_Insightface_iresent100, out_Insightface_iresent100)

            # print('loss : %f' % loss)
            # compute gradients
            loss.backward(retain_graph=True)

            g_noise = momentum * g_noise + (in_variable.grad / in_variable.grad.data.norm(1))
            g_noise = g_noise / g_noise.data.norm(1)

            if i % 2 == 0:
                kernel = gkern(3, 2).astype(np.float32)
                gaussian_blur1 = GaussianBlur(kernel).to(device)
                g_noise = gaussian_blur1(g_noise)
                g_noise = torch.clamp(g_noise, -0.1, 0.1)
            else:
                addition = TVLoss()
                g_noise = addition(g_noise)

            in_variable.data = in_variable.data + (
                    (eps / 255.) * torch.sign(g_noise))  # * torch.from_numpy(mat).unsqueeze(0).float()

            in_variable.grad.data.zero_()  # unnecessary

        # deprocess image
        adv = in_variable.data.cpu().numpy()[0]  # (3, 112, 112)
        perturbation = (adv - in_tensor.cpu().numpy())

        adv = adv * 128.0 + 127.0
        adv = adv.swapaxes(0, 1).swapaxes(1, 2)
        adv = adv[..., ::-1]
        adv = np.clip(adv, 0, 255).astype(np.uint8)

        sample_dir = '/notebooks/Workspace/tmp/pycharm_project_314/TianChi/main_2_output-8-27/'
        if not os.path.exists(sample_dir):
            os.makedirs(sample_dir)

        advimg = sample_dir + path.split('/')[-1].split('.')[-2] + '.jpg'

        cv2.imwrite(advimg, adv)
        print("save path is " + advimg)
        print('cost time is %.2f s ' % (time.time() - start))


if __name__ == '__main__':
    main()

