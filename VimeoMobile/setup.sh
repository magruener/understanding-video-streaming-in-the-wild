
# CHROMEDRIVER
sudo apt-get install unzip

wget -N http://chromedriver.storage.googleapis.com/2.26/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
chmod +x chromedriver

sudo mv -f chromedriver /usr/local/share/chromedriver
sudo ln -s /usr/local/share/chromedriver /usr/local/bin/chromedriver
sudo ln -s /usr/local/share/chromedriver /usr/bin/chromedriver


# PYTHON PACKAGES
pip3 install pandas pgrep selenium


# NODEJS
#
curl -sL https://deb.nodesource.com/setup_10.x | sudo -E bash -
sudo apt install nodejs

# APPIUM DEPENDENCIES
#

apt-get install build-essential curl git m4 ruby texinfo libbz2-dev libcurl4-openssl-dev libexpat-dev libncurses-dev zlib1g-dev


# APPIUM
#
npm install -g appium --unsafe-perm=true --allow-root


# ANDROID STUDIO PRE
#
apt install libcanberra-gtk-module libcanberra-gtk3-module

