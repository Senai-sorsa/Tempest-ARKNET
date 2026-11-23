import numpy as np

from fsval.final_score import leave_one_out, paired_ci


def test_leave_one_out_never_uses_the_flight_it_scores():
    # setup 0 wins overall only through flight 0
    err = np.array([[0.0, 5.0, 5.0], [9.0, 4.0, 4.0]])
    scores, picks = leave_one_out(err)
    assert picks == [1, 0, 0]
    assert scores.tolist() == [9.0, 5.0, 5.0]


def test_paired_ci_is_a_point_when_every_flight_agrees():
    assert paired_ci(np.array([2.0, 3.0]), np.array([1.0, 2.0])) == [1.0, 1.0]
