from imutils.video import VideoStream
from imutils.video import FPS
import matplotlib.pyplot as plt
import argparse
import imutils
import time
import cv2

OPENCV_OBJECT_TRACKERS = {
    "csrt": cv2.TrackerCSRT_create,
    "kcf": cv2.TrackerKCF_create,
    "boosting": cv2.TrackerBoosting_create,
    "mil": cv2.TrackerMIL_create,
    "tld": cv2.TrackerTLD_create,
    "medianflow": cv2.TrackerMedianFlow_create,
    "mosse": cv2.TrackerMOSSE_create,
}


def set_tracker(tracker_name):
    """tracker definition depends on opencv version"""
    # extract the OpenCV version info
    (major, minor) = cv2.__version__.split(".")[:2]
    # if we are using OpenCV 3.2 OR BEFORE, we can use a special factory
    # function to create our object tracker
    # Maybe read the video directly would be faster than reading from input file
    if int(major) == 3 and int(minor) < 3:
        return cv2.Tracker_create("kcf")

    # otherwise, for OpenCV 3.3 OR NEWER, we need to explicity call the
    # approrpiate object tracker constructor:
    # initialize a dictionary that maps strings to their corresponding
    # OpenCV object tracker implementations
    # grab the appropriate object tracker using our dictionary of
    # OpenCV object tracker objects
    return OPENCV_OBJECT_TRACKERS[tracker_name]()


class Box:
    """ wrapper for boxed pupil location from tracker"""

    def __init__(self, boxcoords):
        self.x, self.y, self.w, self.h = boxcoords

    def mid_xy(self):
        return (self.x + self.w / 2, self.y + self.h / 2)


class TrackedFrame:
    """a frame and it's tracking info"""

    def __init__(self, frame, count):
        self.frame = frame
        self.count = count
        self.box = None
        self.success = False

    def set_box(self, box):
        self.box = box
        self.success = self.box.w != 0

    def draw_box(self):
        """add bouding box and pupil center to image
        text added by write image"""
        box_color = (0, 255, 0)
        center_color = (255, 0, 0)
        mid_x, mid_y = self.box.mid_xy()
        x, y, w, h = (self.box.x, self.box.y, self.box.w, self.box.h)
        cv2.rectangle(self.frame, (x, y), (x + w, y + h), box_color, 2)
        # The dot in the center that marks the center of the pupil
        cv2.circle(self.frame, (int(mid_x), int(mid_y)), 5, center_color, -1)


class auto_tracker:
    """eye tracker"""

    def __init__(
        self, video_fname, bbox, tracker_name="kcf", write_img=True, max_frames=9e10
    ):
        # inputs
        self.video_fname = video_fname
        self.iniBB = bbox
        self.tracker_name = tracker_name

        # settings
        self.settings = {"write_img": write_img, "max_frames": max_frames}

        # accumulators
        self.pupil_x = []
        self.pupil_y = []
        self.pupil_count = []
        # output
        self.p_fh = None

        self.tracker = set_tracker(tracker_name)
        # this image is used to construct the image tracker
        first = cv2.imread("input/chosen_pic.png")
        (self.H, self.W) = first.shape[:2]
        print("initializign tracking")
        self.tracker.init(first, self.iniBB)
        (success, box) = self.tracker.update(first)

        # file to save pupil location
        self.p_fh = open("output/points.csv", "w")
        self.p_fh.write("sample,x,y,r\n")

    def find_box(self, frame):
        self.tracker.init(frame, self.iniBB)
        (success, box) = self.tracker.update(frame)

        if success:
            return Box([int(v) for v in box])
        else:
            return Box([0, 0, 0, 0])

    def write_image(self, tframe, fps_measure):
        tframe.draw_box()
        text_color = (0, 0, 255)

        # Information displying on the frame
        info = [
            ("Tracker", self.tracker_name),
            ("Success", "Yes" if tframe.success else "No"),
            ("FPS", "{:.2f}".format(fps_measure)),
        ]

        # Loop over the info tuples and draw them on our frame
        for (i, (k, v)) in enumerate(info):
            text = "{}: {}".format(k, v)
            cv2.putText(
                tframe.frame,
                text,
                (10, self.H - ((i * 20) + 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                text_color,
                2,
            )
            # how the output frame
        cv2.imwrite("output/%015d.png" % tframe.count, tframe.frame)

    def update_position(self, tframe):
        middle_x, middle_y = tframe.box.mid_xy()

        # print(x,y,w,h)
        # TODO: get pupil radius.
        # TODO: if not success is count off? need count for timing
        self.p_fh.write("%d,%d,%d,NA\n" % (tframe.count, middle_x, middle_y))

        self.pupil_x.append(middle_x)
        self.pupil_y.append(middle_y)
        self.pupil_count.append(tframe.count)

    def run_tracker(self):
        count = 0
        vs = cv2.VideoCapture(self.video_fname)
        while True and count < self.settings["max_frames"]:
            count += 1
            fps = FPS().start()

            tframe = TrackedFrame(vs.read()[1], count)
            if tframe.frame is None:
                break
            box = self.find_box(tframe.frame)
            tframe.set_box(box)

            # save positions to textfile and in this object
            self.update_position(tframe)

            # Update the fps counter
            fps.update()
            fps.stop()
            fps_measure = fps.fps()

            # only print every 250 frames. printing is slow
            if count % 250 == 0:
                print(
                    "@ step %d, midde = (%.02f, %02f); %.02f fps"
                    % (count, *tframe.box.mid_xy(), fps_measure)
                )

            if self.settings.get("write_img", True):
                self.write_image(tframe, fps_measure)

            # option to quit with keyboard q
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                exit()

        print("Ending of the analysis")
        if self.p_fh:
            self.p_fh.close()


if __name__ == "__main__":
    bbox = (48, 34, 162, 118)
    track = auto_tracker("input/run1.mov", bbox, write_img=True, max_frames=500)
    track.run_tracker()
