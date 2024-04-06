#!/usr/bin/env bash

INSTALL_DIR=$HOME/.local/bin
mkdir -p $INSTALL_DIR
cp ./cardscan4linux.py $INSTALL_DIR/cardscan4linux

# Check if local binaries area exported
BINARIES=$(echo $PATH)
if [[ ! $BINARIES =~ "$INSTALL_DIR" ]]; then
  echo "PATH=\$PATH:$INSTALL_DIR" >> ~/.profile
  export PATH=$PATH:$INSTALL_DIR
fi

echo "Command installed"