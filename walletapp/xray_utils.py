import traceback

from aws_xray_sdk.core import patch_all, xray_recorder


def run_patch_all():
    xray_recorder.configure(
        plugins=("EC2Plugin", "ECSPlugin"),
        sampling=False,
        streaming_threshold=100,
        daemon_address="127.0.0.1:2000",
    )
    patch_all()


def wrap_in_xray(fcn):
    def wrapper_segment(*args, **kwargs):
        segment = xray_recorder.begin_segment(fcn.__name__)
        try:
            fcn(*args, **kwargs)
        except Exception as e:
            segment.add_exception(e, traceback.extract_stack())
            print(str(e))
            print(traceback.extract_stack())
            print("Logging error and continuing...")
        finally:
            xray_recorder.end_segment()

    return wrapper_segment
