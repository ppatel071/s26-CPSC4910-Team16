#!/bin/bash

cd /home/ec2-user/s26-CPSC4910-Team16
git pull
pip install -r requirements.txt
sudo systemctl restart 4910project.service
