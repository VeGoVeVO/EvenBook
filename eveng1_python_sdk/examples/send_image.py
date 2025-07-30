"""
Example of sending images to G1 glasses


from the documentation:

Image transmission currently supports 1-bit, 576*136 pixel BMP images (refer to image_1.bmp, image_2.bmp in the project). The core process includes three steps:

Divide the BMP image data into packets (each packet is 194 bytes), then add 0x15 command and syncID to the front of the packet, and send it to the dual BLE in the order of the packets (the left and right sides can be sent independently at the same time). The first packet needs to insert 4 bytes of glasses end storage address 0x00, 0x1c, 0x00, 0x00, so the first packet data is ([0x15, index & 0xff, 0x00, 0x1c, 0x00, 0x00], pack), and other packets do not need addresses 0x00, 0x1c, 0x00, 0x00;
After sending the last packet, it is necessary to send the packet end command [0x20, 0x0d, 0x0e] to the dual BLE;
After the packet end command in step 2 is correctly replied, send the CRC check command to the dual BLE through the 0x16 command. When calculating the CRC, it is necessary to consider the glasses end storage address added when sending the first BMP packet.
For a specific example, click the icon in the upper right corner of the App homepage to enter the Features page. The page contains three buttons: BMP 1, BMP 2, and Exit, which represent the transmission and display of picture 1, the transmission and display of picture 2, and the exit of picture transmission and display.


Send bmp data packet
Command Information
Command: 0x15
seq (Sequence Number): 0~255
address: [0x00, 0x1c, 0x00, 0x00]
data0 ~ data194
Field Descriptions
seq (Sequence Number):
Range: 0~255
Description: Indicates the sequence of the current package.
address: bmp address in the Glasses (just attached in the first pack)
data0 ~ data194:
bmp data packet
Bmp data packet transmission ends
Command Information
Command: 0x20
data0: 0x0d
data1: 0x0e
Field Descriptions
Fixed format command： [0x20, 0x0d, 0x0e]
CRC Check
Command Information
Command: 0x16
crc
Field Descriptions
crc: The crc check value calculated using Crc32Xz big endian, combined with the bmp picture storage address and picture data.
"""

import asyncio
from connector import G1Connector
from services import DisplayService

async def main():
    """
    Demonstrates sending BMP images to G1 glasses
    
    Protocol details:
    - Supports 1-bit, 576x136 pixel BMP images
    - Images are divided into 194-byte packets
    - First packet includes storage address
    - Requires CRC check after transmission
    """
    glasses = G1Connector()
    await glasses.connect()
    
    display = DisplayService(glasses)
    await display.send_image("path/to/image.bmp")

if __name__ == "__main__":
    asyncio.run(main())
