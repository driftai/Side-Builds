import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.enumerate_raw_input_keyboards import enumerate_keyboards, IS_WINDOWS


def test_raw_input_keyboards_shape():
    keyboards = enumerate_keyboards()
    assert isinstance(keyboards, list)
    if IS_WINDOWS:
        # At least one keyboard (physical/system) is typically present
        for k in keyboards:
            assert "handle" in k
            assert "name" in k
            assert "is_omnipad" in k
            assert isinstance(k["is_omnipad"], bool)
    print("  [PASS] Raw Input keyboard device enumeration structure verified")


def main():
    print("\n" + "=" * 60)
    print("  TEST: Windows Raw Input Keyboard Device Enumeration")
    print("=" * 60)
    test_raw_input_keyboards_shape()
    print("  >>> RAW INPUT TEST COMPLETED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    main()
