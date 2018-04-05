# run in home directory ~
wget -r -np -A.zip -e robots=off https://childes.talkbank.org/data-xml/
cd childes.talkbank.org/data-xml
find . -name "*.zip" | while read filename; do unzip -o -d "`dirname "$filename"`" "$filename"; done;
