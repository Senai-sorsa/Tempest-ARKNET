"""A flight's tier follows its measurement and motor, nothing else."""
from fsval.tiers import motor_class, tier


def test_motor_class_reads_the_maker_tag():
    assert motor_class("P9381  (LR-EX)") == "experimental"
    assert motor_class("O10000  (Hist)") == "historic"
    assert motor_class("J570W  (AT)") == "commercial"


def test_tier_takes_the_worst_doubt():
    assert tier("Gibb", "I284W  (AT)") == "A"
    assert tier("IonDrive", "K550W  (AT)") == "B"
    assert tier("Kinsel_P4935_A-601_Rocket", "P4935  (LR-EX)") == "B"
    assert tier("Qu8k", "Q18000  (DEAP-EX)") == "C"
