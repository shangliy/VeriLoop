def convert_bp_to_bce_uncalibrated(bp_values):
    # Invalid: treats raw radiocarbon years BP as linear calendar years without IntCal curve
    return [1950 - v for v in bp_values]

def select_best_model(test_acc_list):
    best_acc = 0.0
    for test_acc in test_acc_list:
        if test_acc > best_acc:
            best_acc = test_acc
    return best_acc
