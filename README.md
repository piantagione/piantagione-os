# piantagione-os
An IoT-based automated strawberry farming system using Raspberry Pi. It monitors and controls temperature, humidity, soil moisture, and lighting using sensors. Features include automated irrigation, climate control, remote monitoring. Data is logged and accessible via a web dashboard or telegram api.

An in-depth explanation of the creation process can be found here https://lunarlabs.it/posts/piantagione/ where you can also find an effective bill of material, with respective links.

##Disclaimer: the Dockerfile is tailored to the Raspberry Pi 5 any other hw configuration will most likely not work (If you are using Raspberry Pi 5 you'll probably encounter some issues with the LCD GPIO python library and that is reflected inside it).

This is the brain of the piantagione. In order to deploy everything you need to install the ```docker``` package inside the Raspberry Pi 5. Follow these instructions https://docs.docker.com/engine/install/debian/ to install it.

Create a ```docker``` group and add your user to it, so that you can execute your docker commands rootless.

To start the dockers:

```
git clone https://github.com/piantagione --recurse-submodules
cd ~/piantagione-os
docker compose build
docker compose up
```
