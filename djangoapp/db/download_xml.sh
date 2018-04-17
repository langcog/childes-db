# run in home directory ~
# also i usually add providence because remote xml store does not have it anymore
wget -r -np -A.zip -e robots=off https://childes.talkbank.org/data-xml/
cd childes.talkbank.org/data-xml
find . -name "*.zip" | while read filename; do unzip -o -d "`dirname "$filename"`" "$filename"; done;
