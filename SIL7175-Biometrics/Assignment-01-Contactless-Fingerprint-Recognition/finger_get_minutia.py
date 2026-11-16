import argparse
from nsdk.media import NImage, NPixelFormat
from nsdk.biometrics import FingerEngine
from pynsdk.licensing import NLicense, NLicenseManager
import cv2
import numpy as np

def main(args):
    rad = np.pi / 180.
    if not args.file_name:
        print ("File name is not provided")
        return 

    ##=========================================================================
    ## TRIAL MODE
    ##=========================================================================
    ## By default trial is disabled - you have to explicitly set it to enable it.

    is_trial_mode = True
    NLicenseManager.set_trial_mode(is_trial_mode)
    print(f"Trial mode: {is_trial_mode}")

    ##=========================================================================

    license = "FingerExtractor"
    if not NLicense.obtain("/local", 5000, license):
        print(f"Failed to obtain license: {license}")
        return
    print(f"License obtained successfully: {license}")

    engine = FingerEngine()
    nimage = NImage(args.file_name)
    _, finger_templates = engine.extract_finger(nimage)
    minutia = finger_templates[0].fingers.records[0].minutiae
    np_image = nimage.to_numpy(NPixelFormat.rgb_8u)

    for idx, minutiae in enumerate(minutia):
        x1 = minutiae.x
        y1 = minutiae.y
        angle = minutiae.angle
        x2 = int(x1 + 15 * np.cos(angle * 1.411764706 * rad))
        y2 = int(y1 + 15 * np.sin(angle * 1.411764706 * rad))
        cv2.line(np_image, (x1, y1), (x2, y2), (0, 0, 255), 1)
        cv2.circle(np_image, (x1, y1), 3, (0, 0, 255), thickness=-1, lineType=8, shift=0)
        print (f"{idx} minutiae cordinate ({minutiae.x}, {minutiae.y}) angle {minutiae.angle}")

    cv2.imshow("finger", np_image)
    cv2.waitKey(-1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Get finger minutiare image')
    parser.add_argument('--file_name', type=str, default="", help='file name')
    args_ = parser.parse_args()
    main(args_)