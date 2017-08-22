#!/bin/sh

# script interval
interval=$1

# check system type
command -v /usr/bin/dpkg --search /usr/bin/dpkg >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "System is RPM based"
    os="rpm"
else
    echo "System is debian based"
    os='debian'
fi

# check if pip is installed or not
command -v pip >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Pip is not installed.. Installing pip"
    # check system type
    if [ $os == "rpm" ]; then
        sudo yum install -Y epel-release
        sudo yum install python-pip
    else
        sudo apt-get install -Y epel-release
        sudo apt-get install python-pip
    fi

    echo "Pip is installed. Now checking/installing required packages.."        
else
    echo "Pip is available. Now checking/installing required packages.."        
fi

# install required packages - make sure you have sudo privileges
pip list | grep -F configparser >/dev/null 2>&1
if [ $? -ne 0 ]; then
    sudo pip install configparser
fi

pip list | grep -F graphitesend >/dev/null 2>&1
if [ $? -ne 0 ]; then
    sudo pip install graphitesend
fi

pip list | grep -F requests >/dev/null 2>&1
if [ $? -ne 0 ]; then
    sudo pip install requests
fi 

echo "Required packages are Available"

# Configure system service
if [ $os = "rpm" ]; then
    sudo cp Prestodb_emitter.py /usr/bin/Prestodb_emitter.py
    sudo chmod +x /usr/bin/Prestodb_emitter.py
    sudo cp Presto_config.py /usr/bin/Presto_config.py
    sudo echo "
    [Unit]
    Description=Presto_Emitter

    [Service]
    Type=idle
    ExecStart=/usr/bin/Prestodb_emitter.py /usr/bin/Prestodb_emitter.py $interval

    [Install]
    WantedBy=multi-user.target
    " > presto_emitter.service
    sudo cp presto_emitter.service /usr/lib/systemd/system/presto_emitter.service
    rm presto_emitter.service
    sudo systemctl daemon-reload
    sudo systemctl enable presto_emitter.service

else
    sudo cp Prestodb_emitter.py /usr/bin/Prestodb_emitter.py
    sudo chmod +x /usr/bin/Prestodb_emitter.py
    sudo cp Presto_config.py /usr/bin/Presto_config.py
    sudo echo "
    [Unit]
    Description=Presto_Emitter

    [Service]
    Type=idle
    ExecStart=/usr/bin/Prestodb_emitter.py /usr/bin/Prestodb_emitter.py $interval

    [Install]
    WantedBy=multi-user.target
    " > presto_emitter.service
    sudo cp presto_emitter.service /lib/systemd/system/presto_emitter.service
    rm presto_emitter.service
    sudo systemctl daemon-reload
    sudo systemctl enable presto_emitter.service
fi

    
