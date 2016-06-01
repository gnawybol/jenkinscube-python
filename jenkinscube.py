from __future__ import print_function

import argparse
import jenkins
import os
import statuscube
import serial.tools.list_ports
import sys
import time

COLOR_TO_STATE = {
    'blue': statuscube.STATE_SUCCESS,
    'yellow': statuscube.STATE_ERROR,
    'red': statuscube.STATE_FAULT,
    'aborted': statuscube.STATE_NONE,
    'notbuilt': statuscube.STATE_NONE,
    'blue_anime': statuscube.STATE_WORKING,
    'red_anime': statuscube.STATE_WORKING,
    'yellow_anime': statuscube.STATE_WORKING,
    'notbuilt_anime': statuscube.STATE_WORKING,
    'aborted_anime': statuscube.STATE_WORKING,
}


def get_state(color):
    state = COLOR_TO_STATE.get(color)
    if state is None:
        raise ValueError('Unknown color', color)
    return state


def map_pixel_to_state(colors):
    colors_num = len(colors)
    pixels_num = len(statuscube.ALL_PIXELS)

    assert colors_num <= pixels_num

    if colors_num == 1:
        return {statuscube.PIXEL_OMNI: get_state(colors[0])}

    # Populate seed pixels
    pixel_to_state = dict()
    for index, color in enumerate(colors):
        pixel_index = int(round((index * pixels_num) / float(colors_num)))
        pixel = statuscube.ALL_PIXELS[pixel_index]
        state = get_state(color)
        pixel_to_state[pixel] = state

    # ..and fill in the blanks
    last_state = None
    for pixel in statuscube.ALL_PIXELS:
        if pixel in pixel_to_state:
            last_state = pixel_to_state[pixel]
            continue

        pixel_to_state[pixel] = last_state

    return pixel_to_state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='buildcube Jenkins poller')
    parser.add_argument('serial_port', metavar='serial_port', type=str,
                        choices=list(p[0] for p in serial.tools.list_ports.comports()), help='Serial port.')
    parser.add_argument('--server', dest='server', action='store', type=str, help='Server URL. [JENKINS_SERVER]')
    parser.add_argument('--username', dest='username', action='store', type=str, help='Username. [JENKINS_USERNAME]')
    parser.add_argument('--password', dest='password', action='store', type=str, help='Password. [JENKINS_PASSWORD]')
    parser.add_argument('--interval', dest='interval', action='store', default=60, type=int,
                        help='Polling interval in seconds.')
    parser.add_argument('jobs', metavar='job', type=str, nargs='+',
                        help='Job name(s). Maximum {}'.format(len(statuscube.ALL_PIXELS)))
    args = parser.parse_args()

    if len(args.jobs) > len(statuscube.ALL_PIXELS):
        sys.exit('Too many jobs specified!')

    server = args.server or os.environ.get('JENKINS_SERVER')
    username = args.username or os.environ.get('JENKINS_USERNAME')
    password = args.password or os.environ.get('JENKINS_PASSWORD')
    conn = jenkins.Jenkins(server, username=username, password=password)

    cube = statuscube.StatusCube(args.serial_port)

    pixel_to_state = dict()

    while True:
        # TODO: Should handle errors somehow.
        job_colors = [conn.get_job_info(job).get('color') for job in args.jobs]

        for pixel, state_new in map_pixel_to_state(job_colors).items():
            state_last = pixel_to_state.get(pixel)

            if state_new != state_last:
                cube.set_pixel_state(pixel, state_new)
                pixel_to_state[pixel] = state_new

        time.sleep(args.interval)
