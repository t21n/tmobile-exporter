from app import fetch_telekom_usage
from app import main


def test_fetch_usage():
    fetch_telekom_usage()
    # Read the current value of the gauge
    value = main.bytes_remaining._value.get()  # <- direct internal access

    assert isinstance(value, (int, float))
    assert value > 0