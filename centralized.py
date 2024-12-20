import time
import numpy as np

from data_reader.data_reader import get_data
from models.get_model import get_model
from statistic.collect_stat import CollectStatistics
from util.sampling import MinibatchSampling

from config import *

if use_min_loss:
    raise Exception('use_min_loss should be disabled in centralized case.')

model = get_model(model_name)
if hasattr(model, 'create_graph'):
    model.create_graph(learning_rate=step_size)

if time_gen is not None:
    use_fixed_averaging_slots = True
else:
    use_fixed_averaging_slots = False

if single_run:
    stat = CollectStatistics(results_file_name=single_run_results_file_path, is_single_run=True)
else:
    stat = CollectStatistics(results_file_name=multi_run_results_file_path, is_single_run=False)

for sim in sim_runs:

    if batch_size < total_data:  
        train_image, train_label, test_image, test_label, train_label_orig = get_data(dataset, total_data,
                                                                                      dataset_file_path)
        sampler = MinibatchSampling(np.array(range(0, len(train_label))), batch_size, sim)
    else:
        sampler = None

    if batch_size >= total_data:  
        train_image, train_label, test_image, test_label, train_label_orig = get_data(dataset, total_data,
                                                                                      dataset_file_path, sim_round=sim)
        train_indices = np.array(range(0, len(train_label)))

    stat.init_stat_new_global_round()

    dim_w = model.get_weight_dimension(train_image, train_label)
    w_init = model.get_init_weight(dim_w, rand_seed=sim)
    w = w_init

    w_min_loss = None
    loss_min = np.inf

    print('Start learning')

    total_time = 0    
    total_time_recomputed = 0  
    it_each_local = None

    while True:
        time_total_all_start = time.time()
        w_prev = w

        if batch_size < total_data:
            train_indices = sampler.get_next_batch()

        grad = model.gradient(train_image, train_label, w, train_indices)

        w = w - step_size * grad

        if True in np.isnan(w):
            print('*** w_global is NaN, using previous value')
            w = w_prev   

            if use_min_loss:
                loss_latest = model.loss(train_image, train_label, w, train_indices)
                print('*** Loss computed from data')
        else:
            if use_min_loss:
                try:
                    loss_latest = model.loss_from_prev_gradient_computation()
                    print('*** Loss computed from previous gradient computation')
                except:
                    loss_latest = model.loss(train_image, train_label, w, train_indices)
                    print('*** Loss computed from data')

        if use_min_loss:
            if (batch_size < total_data) and (w_min_loss is not None):
                loss_min = model.loss(train_image, train_label, w_min_loss, train_indices)

            if loss_latest < loss_min:
                loss_min = loss_latest
                w_min_loss = w

            print("Loss of latest weight value: " + str(loss_latest))
            print("Minimum loss: " + str(loss_min))

        time_total_all_end = time.time()
        time_total_all = time_total_all_end - time_total_all_start
        time_one_iteration_all = max(0.0, time_total_all)

        print('Time for one local iteration:', time_one_iteration_all)

        if use_fixed_averaging_slots:
            it_each_local = max(0.00000001, time_gen.get_local(1)[0])
        else:
            it_each_local = max(0.00000001, time_one_iteration_all)

        total_time_recomputed += it_each_local

        total_time += time_total_all

        stat.collect_stat_end_local_round(None, np.nan, it_each_local, np.nan, None, model, train_image, train_label,
                                          test_image, test_label, w, total_time_recomputed)

        if total_time_recomputed >= max_time:
            break

    if use_min_loss:
        w_eval = w_min_loss
    else:
        w_eval = w

    stat.collect_stat_end_global_round(sim, None, np.nan, total_time, model, train_image, train_label,
                                       test_image, test_label, w_eval, total_time_recomputed)
