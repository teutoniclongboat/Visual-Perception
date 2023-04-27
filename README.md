
# Xilinx: Smart City Application

In this release, we're using Xilinx 2021.1 (Vitis, Vivado, Petlalinux). In this tutorial guide, I will not focused on the nitty gritty steps of setting up and running; rather, it is overall the design aspect that build up the project. But you can still be guarenteed a easy running solution, which I will packaged easily for use. You can download [KV260YOUNEED](https://drive.google.com/file/d/1HWLLi2nrYF7WYJN76PPqqpsAUN0CyA4C/view?usp=share_link) and just copy to the corresponding place in KV260 once inital bootup. Remember to process everything as **root** user.

The bitstream or platform we build are from [kria-vitis-platforms](https://github.com/Xilinx/kria-vitis-platforms/tree/release-2021.1). The end application **gst_4k** require only **aibox-reid** which is based on platform **vcuDecode_vmixDP**.

Naturally, a video platform consists of three different sections: input, logic, output. For vcuDecode_vmixDP we can seperate to four different pipelines:
- capture pipeline - input
- video processing (vcu decode h.264 for video sending through network)
- acceleration - logic
- output pipeline

Below content will be based on [Kria KV260 documentation](https://xilinx.github.io/kria-apps-docs/kv260/2021.1/build/html/index.html). Please refer that for more detailed information.

The design has a **platform** and **integrated accelerator functions (overlay)**. The platform consists of capture pipeline, output pipeline and video decoding functions. This approach makes the design leaner and provides a user maximum Programmable Logic (PL) for the accelerator development. The platform supports input streams from IP camera and as well as file sources. The output can be displayed on DisplayPort/HDMI monitor. Video decoding/decompression and encoding/compression is performed on hard blocks VCU since it is most performant to do so.

Below is the four different pipeline:
![](https://i.imgur.com/wmP7VEx.png)

And here is the overall end-to-end pipeline:
![](https://i.imgur.com/1IW87Vi.png)

## Hardware Architecture:

### Platform

Recapture the four pipelines:

![](https://i.imgur.com/94ZuF8x.png)

- Capture pipeline: This comprises of pipelines through which video data is captured. Ethernet pipeline receiving encoded streams from mutiple cameras via RTSP (PS). For more information refer to GEM Ethernet chapters in the Zynq UltraScale+ Device Technical Reference Manual ([UG1085](https://www.xilinx.com/support/documentation/user_guides/ug1085-zynq-ultrascale-trm.pdf)).

- Video processing pipeline: This comprises of VCU decoder for decompressing four encoded streams of data (Hard IP). For more information on Video Processing pipelines, refer to the Video Codec Unit LogiCORE IP Product Guide ([PG252](https://docs.xilinx.com/r/lvlXZyXF92ne0AASBP0ysw/root)).

- Display/Output pipeline: An output pipeline reads video frames from memory and sends the frames to a sink. In this case the sink is a display port in the PS. DisplayPort pipeline (PL + PS). 
![](https://i.imgur.com/gM3Cmol.png)
One thing to note is that the video mixer ip is configured to support blending of up to four overlay layers into one single output video stream. For more information refer to the Video Mixer LogiCORE IP Product Guide ([PG243](https://www.xilinx.com/support/documentation/ip_documentation/v_mix/v1_0/pg243-v-mix.pdf)).

- (Overlay) Accelerator pipeline : This comprises of overlay accelerator functions integrated into the platform using Vitis. The Deep Learning Processing Unit (DPU) IP runs different Neural Network models (PL). The Pre-Processing block modifies the input data as required by the Network (PL).

### Accelerator
There are two PL componenet in the Accelerator pipeline:
- Pre-Processing block: The desgin uses Vitis Vision Library functions to build the pre-processing block. The Vitis functions used are, cvtcolor, resize, and blobfromimage.
  - cvtcolor: Reads an NV12 video frame and converts the color format to BGR
  - Resizing: Scales down the original 4K/1080p frame to at most 720x720
  - Quantizing (blobfromimage): Performs linear transformation (scaling and shifting) to each pixel of BGR frame to satisfy DPU input requirement
![](https://i.imgur.com/lCDmuD5.png)

- DPU: For this design, the following features should be enabled: Channel augmentation, Depth-wise convolution, Average pooling, Relu, LeakyRelu and Relu6, URAM enable.
To learn more about the DPU, please refer the [PG338](https://www.xilinx.com/support/documentation/ip_documentation/dpu/v3_2/pg338-dpu.pdf)
![](https://i.imgur.com/F4noboS.png)

## Software Architecture:

### Platform
This section is about application processing unit (APU) Linux software stack. The stack and vertical domains are shown in the following figure.
![](https://i.imgur.com/5YPSrJ3.png)

It is horizontally divided into application, middleware, and os layer, and vertically the software components are divided by domain. To be noted, middleware implements and exposes domain-specific functionality by means of GStreamer plugins to interface with the application layer and provides access to kernel frameworks.

It works like this: RTSP stream or a file source is pipelined to the Codec. (Although we will not using rtsp in this application, but functionality-wise, rtspsrc plugin is used as client to stream from ip camera if used and rtph264depay plugin extracts H264 video from RTP packets and streamed into the vcu).

Then VCU software stack consists of a custom kernel module (xlnx_vcu, allegro, al5e(encode), al5d(decode)) and a custom user space library known as Control Software (CtrlSW). The OpenMAX (OMX) integration layer (IL) is integrated on top of CtrlSW, and the GStreamer framework is used to integrate the OMX IL component and other multimedia elements. OpenMAX (Open Media Acceleration) is a cross-platform API that provides a comprehensive streaming media codec and application portability by enabling accelerated multimedia components. Again for more information, refer to VCU Product guide.

Linux kernel and user-space frameworks for display and graphics are intertwined and the software stack can be quite complex with many layers and different standards / APIs. On the kernel side, the display and graphics portions are split with each having their own APIs. However, both are commonly referred to as a single framework, namely DRM/KMS. This split is advantageous, especially for SoCs that often have dedicated hardware blocks for display and graphics. The display pipeline driver responsible for interfacing with the display uses the kernel mode setting (KMS) API and the GPU responsible for drawing objects into memory uses the direct rendering manager (DRM) API. Both APIs are accessed from user-space through a single device node.

![](https://i.imgur.com/zmZwSoq.png)


### Accelerator
Vitis AI 1.4.0 is the core underlying component to access the AI inference capability provided by Xilinx DPU.

To access DPU and other PL hardware accelerator functions from GStreamer, Xilinx developed Vitis Video Analysis SDK (VVAS) to provide convinient and customizable GStreamer plugins for it.

For gst_4k application, gstreamer will branch into 4 pipelines:
1. segmentation (management branch, top left)
2. status recording (management branch, top right)
3. refindet + openpose/reid (branch1, bottom left)
4. yolo2 (branch2, bottom right)

![](https://i.imgur.com/C9zf27B.png)

But the pipeline is flexible. More about the intended use about each branch can refer to the [original paper](https://www.hackster.io/yufan-lu/all-in-one-self-adaptive-computing-platform-for-smart-city-933ff2#toc-4--gstreamer-video-processing-pipes-in-the-demo-14).


## Petalinux BSP
It is modified based on bsp from 2021.1 and you can download [BSP](https://drive.google.com/file/d/12E-d7GQnHejN_8SWhM4nR8AtScM6HZ_c/view?usp=share_link).

For petalinux here are the major changes we make:
1. enable systemd and mosquitto (not necessary)
2. adding thingsboard-gateway receipe (not used in the end)
3. changing initramfs size to 256 MB
4. disable dropbear and use openssh instead
5. adding gnu toolchain to enable tvm compiling
6. other user receipe (refer to project-spec/meta-user)


** Advise on petalinux project:
- Run build before adding anything to the project to see if any error happened. If something occured, refer to any fix or update that need to apply or simply just google it.
- When packaging into wic format, you can change partition size for SD card image in wks file where default location is in build/wks/rootfs.wks (also change --ondisk from mmcblk0 to mmcblk1)
- whenever you power on KV260 you need to restart the **dfx manager** in order for xmutil to be functional in this release. (systemctl restart dfx-mgr.service)

## ThingsBoard Integration
We have three application that can use mqtt to commuicate with the thingsboard server:
1. provision
2. sending data
3. ota

Basically, provision is to register device on server and it will give you a unique token which will later used to identify the machine. Also we can send status(fps, power, temperature) when running gst_4k alongside. For OTA, it is just a demo that if you pack your firmware/software in the structure defined in **ota/update.sh**, then once it uploads to thingsboard server, it will automatically download and decompress and put the things in the right place.:)

In ota the idea is basically this 
1. subscribe to shared attributes (v1/devices/me/attributes/response/+) waiting for update
2. request info about current firmware and new firmware info (v1/devives/me/attributes/request/$request_id)
3. subscribe to firmware chunck (v2/fw/me/response/+/chunk/+) and initiate request (v2/fw/requests/\$request_id/chunk/$chunkindex)
4. sending ota status to both client attributes and telemetry
