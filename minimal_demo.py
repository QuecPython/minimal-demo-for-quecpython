# Copyright (c) Quectel Wireless Solution, Co., Ltd.All Rights Reserved.
 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
 
#     http://www.apache.org/licenses/LICENSE-2.0
 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A minimal demo of QuecPython"""

import log
import _thread
import usocket
import checkNet
from queue import Queue

import utime
from machine import UART, Pin


# Create an object for log output
# Description: https://python.quectel.com/doc/API_reference/en/syslib/log.html
logger = log.getLogger(__name__)
log.basicConfig(level=log.DEBUG)


# Demo configuration
DEMO_CONFIG = {
    "PROJECT_NAME": "QuecPython_DEMO",
    "PROJECT_VERSION": "1.0.0",
    "SERVER": {
        "host": "220.180.239.212",
        "port": "8305",
        "timeout": 5,
        "keep_alive": 5
    },
    "UART": {
        "port": 2,
        "baudrate": 115200,
        "bytesize": 8,
        "parity": 0,
        "stopbits": 1,
        "flowctl": 0
    },
    "LED": {
        "GPIOn": 16
    }
}


class Demo(object):
    """Demo Class with simple features:
        - tcp transmission
        - serial read/write
    """

    def __init__(self, name, config=None):
        self.name = name
        self.config = config or DEMO_CONFIG
        self.__uart = None
        self.__sock = None

        # Class <Pin> is used to control I/O pins.
        # Here we use <Pin> to control the blinking of LED.
        # Description: https://python.quectel.com/doc/API_reference/en/peripherals/machine.Pin.html
        self.__led = Pin(getattr(Pin, 'GPIO{}'.format(self.config['LED']['GPIOn'])), Pin.OUT, Pin.PULL_PD, 0)
        self.__led_blink_thread_id = None

    def __str__(self):
        return 'Demo(name=\"{}\")'.format(self.name)

    def __uart_cb(self, args):
        """This callback function will be triggered when data is received on the UART.

        :param args: tuple, as below explain:
            args[0]: Whether the data is received successfully. 0 - Received successfully; Others - Receiving failed
            args[1]: Port for receiving data.
            args[2]: How much data is returned.
        :return:
        """
        # get unread data size
        unread_data_size = self.__uart.any()
        # read all data as possible
        data = self.__uart.read(unread_data_size)
        logger.debug('read data from serial: {}'.format(data))
        try:
            # socket send method
            # Description: https://python.quectel.com/doc/API_reference/en/stdlib/usocket.html
            length = self.__sock.send(data)
        except Exception as e:
            logger.error('send data to cloud failed! pls check your connection. error: {}'.format(e))
        else:
            self.blink(50, 50, 20)
            logger.debug('send data to cloud successfully, actual sent bytes size: {}'.format(length))

    def open_serial(self):
        try:
            # UART communication
            # Description: https://python.quectel.com/doc/API_reference/en/peripherals/machine.UART.html
            self.__uart = UART(
                getattr(UART, 'UART{}'.format(self.config['UART']['port'])),
                self.config['UART']['baudrate'],
                self.config['UART']['bytesize'],
                self.config['UART']['parity'],
                self.config['UART']['stopbits'],
                self.config['UART']['flowctl']
            )
            self.__uart.set_callback(self.__uart_cb)  # register UART callback
        except Exception as e:
            logger.error('open serial failed: {}'.format(e))
        else:
            logger.info('open serial successfully.')

    def __sock_recv_thread_worker(self):
        while True:
            try:
                # socket recv method
                # Description: https://python.quectel.com/doc/API_reference/en/stdlib/usocket.html
                data = self.__sock.recv(1024)
                logger.debug('read data from socket: {}'.format(data))

                try:
                    # uart write method
                    # Description: https://python.quectel.com/doc/API_reference/en/peripherals/machine.UART.html
                    length = self.__uart.write(data)
                except Exception as e:
                    logger.error('send data to serial failed! pls check serial port status. error: {}'.format(e))
                else:
                    logger.debug('send data to serial successfully, actual sent bytes size: {}'.format(length))
            except Exception as e:
                if isinstance(e, OSError) and e.args[0] == 110:
                    # read timeout.
                    continue
                else:
                    logger.critical('socket read failed! error: {}; recv thread has broken!'.format(e))
                    break

    def connect_cloud(self):
        try:
            # read server configure
            host = self.config['SERVER']['host']
            port = self.config['SERVER']['port']
            timeout = self.config['SERVER']['timeout']
            keep_alive = self.config['SERVER']['keep_alive']

            # we parse the domain name of DNS.
            # Description: https://python.quectel.com/doc/API_reference/en/stdlib/usocket.html
            rv = usocket.getaddrinfo(host, port)
            if not rv:
                raise ValueError('DNS detect error for addr: {},{}'.format(host, port))
            ip, port = rv[0][4]

            # tcp socket creating flow
            # Description: https://python.quectel.com/doc/API_reference/en/stdlib/usocket.html
            self.__sock = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
            self.__sock.connect((ip, port))
            self.__sock.settimeout(timeout)
            self.__sock.setsockopt(usocket.SOL_SOCKET, usocket.TCP_KEEPALIVE, keep_alive)
        except Exception as e:
            logger.error('connect cloud failed: {}'.format(e))
        else:
            _thread.start_new_thread(self.__sock_recv_thread_worker, ())
            logger.info('connect cloud successfully.')

    def blink(self, on_remaining, off_remaining, count):
        """start LED blink"""
        if self.__led_blink_thread_id and _thread.threadIsRunning(self.__led_blink_thread_id):
            # avoid repeating
            return

        def led_blink_thread_worker(on_remaining, off_remaining, count):
            """actual thread work function; make the LED on/off"""
            while count > 0:
                self.__led.write(1)  # on led
                utime.sleep_ms(on_remaining)
                self.__led.write(0)  # off led
                utime.sleep_ms(off_remaining)
                count -= 1

        # we blink LED light in a thread
        self.__led_blink_thread_id = _thread.start_new_thread(
            led_blink_thread_worker,
            (on_remaining, off_remaining, count)
        )

    def run(self):
        logger.info('{} run...'.format(self))
        self.open_serial()
        self.connect_cloud()


if __name__ == '__main__':
    # initialize Demo Object
    demo = Demo('Quectel')

    # poweron print once
    checknet = checkNet.CheckNetwork(
        demo.config['PROJECT_NAME'],
        demo.config['PROJECT_VERSION'],
    )
    checknet.poweron_print_once()

    # check network until ready
    while True:
        codes = checkNet.waitNetworkReady()
        if codes == (3, 1):
            logger.info('network has been ready.')
            break
        else:
            print('network not ready, error code is {}.'.format(codes))

    # Demo application run forever
    demo.run()
