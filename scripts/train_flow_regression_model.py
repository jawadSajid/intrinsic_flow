from __future__ import division, print_function

import torch
from data.data_loader import CreateDataLoader
from models.flow_regression_model import FlowRegressionModel
from options.flow_regression_options import TrainFlowRegressionOptions
from util.visualizer import FlowVisualizer
from util.loss_buffer import LossBuffer

import util.io as io
import os
import sys
import numpy as np
import tqdm

# parse and store options
parser = TrainFlowRegressionOptions()
opt = parser.parse()
parser.save()
# create model
model = FlowRegressionModel()
model.initialize(opt)
# save terminal line
io.save_str_list([' '.join(sys.argv)], os.path.join(model.save_dir, 'order_line.txt'))
# create data loader
train_loader = CreateDataLoader(opt, split='train')
val_loader = CreateDataLoader(opt, split='test')
# create visualizer
visualizer = FlowVisualizer(opt)


# set "saving best"
best_info = {
    'meas': 'EPE',
    'type': 'min',
    'best_value': 0,
    'best_epoch': -1
}

# set continue training
if not opt.resume_train:
    total_steps = 0
    epoch_count = 1
else:
    last_epoch = int(opt.last_epoch)
    total_steps = len(train_loader)*last_epoch
    epoch_count = 1 + last_epoch

for epoch in tqdm.trange(epoch_count, opt.niter+opt.niter_decay+1, desc='Epoch'):
    model.update_learning_rate()
    model.train()
    for i,data in enumerate(tqdm.tqdm(train_loader, desc='Train')):
        total_steps += 1
        model.set_input(data)
        model.optimize_parameters(check_grad=(total_steps%opt.check_grad_freq==0))
        
        if total_steps % opt.display_freq == 0:
            train_error = model.get_current_errors()
            tqdm.tqdm.write(visualizer.print_train_error(
                iter_num = total_steps,
                epoch = epoch, 
                num_batch = len(train_loader), 
                lr = model.optimizers[0].param_groups[0]['lr'], 
                errors = train_error))
        
    if epoch % opt.test_epoch_freq == 0:
        # model.get_current_errors() #erase training error information
        model.output = {}
        loss_buffer = LossBuffer(size=len(val_loader))
        model.eval()
        for i, data in enumerate(tqdm.tqdm(val_loader, desc='Test')):
            model.set_input(data)
            model.test(compute_loss=True)
            loss_buffer.add(model.get_current_errors())
        test_error = loss_buffer.get_errors()
        tqdm.tqdm.write(visualizer.print_test_error(iter_num=total_steps, epoch=epoch, errors=test_error))
        # save best
        if best_info['best_epoch']==-1 or (test_error[best_info['meas']].item()<best_info['best_value'] and best_info['type']=='min') or (test_error[best_info['meas']].item()>best_info['best_value'] and best_info['type']=='max'):
            best_info['best_epoch'] = epoch
            best_info['best_value'] = test_error[best_info['meas']].item()
            model.save('best')
        tqdm.tqdm.write(str(best_info))
    
    if epoch % opt.vis_epoch_freq == 0:
        model.eval()
        num_vis_batch = int(1.*opt.nvis/opt.batch_size)
        visuals = None
        for i, data in enumerate(train_loader):
            if i == num_vis_batch:
                break
            model.set_input(data)
            model.test(compute_loss=True)
            v = model.get_current_visuals()
            if visuals is None:
                visuals = v
            else:
                for name, item in v.iteritems():
                    visuals[name][0] = torch.cat((visuals[name][0], item[0]), dim=0)
        tqdm.tqdm.write('visualizing training sample')
        visualizer.visualize_image(epoch=epoch, subset='train', visuals=visuals)

        visuals = None
        for i, data in enumerate(val_loader):
            if i == num_vis_batch:
                break
            model.set_input(data)
            model.test(compute_loss=True)
            v = model.get_current_visuals()
            if visuals is None:
                visuals = v
            else:
                for name, item in v.iteritems():
                    visuals[name][0] = torch.cat((visuals[name][0], item[0]), dim=0)
        tqdm.tqdm.write('visualizing test sample')
        visualizer.visualize_image(epoch=epoch, subset='test', visuals=visuals)
    
    if epoch % opt.save_epoch_freq == 0:
        model.save(epoch)
    model.save('latest')

print(best_info)


        
