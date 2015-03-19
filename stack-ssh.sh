#!/bin/bash

export tgt=`stat -f "%N" ~/.ssh/config`
if [ -e "$tgt" ]; then

    export backup="${tgt}_backup_`date +%s`"
    echo "backing up $tgt to $backup"
    cp $tgt $backup
fi


echo "Populating $tgt with AWS EC2 instances"
$ROOT/armada/aws-ssh-config/aws-ssh-config --tags "aws:cloudformation:stack-name,Name" | tee "$tgt"

echo "Done."

