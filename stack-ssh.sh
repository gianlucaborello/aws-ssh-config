#!/bin/bash

touch ~/.ssh/config

if [[ "$OSTYPE" == linux* ]]; then
	export tgt=$(readlink -f ~/.ssh/config)
else
	export tgt=$(stat -f "%N" ~/.ssh/config)
fi

if [ -e "$tgt" ]; then

    export backup="${tgt}_backup_`date +%s`"
    echo "backing up $tgt to $backup"
    cp $tgt $backup
fi

[ ! -z "$STACK_SSH_KEY" ] && ssh_key_arg="--ssh-key ${STACK_SSH_KEY}"
[ ! -z "$STACK_SSH_USER" ] && ssh_user_arg="--ssh-user ${STACK_SSH_USER}"

echo "Populating $tgt with AWS EC2 instances"
$ROOT/aws-ssh-config/aws-ssh-config --tags "aws:cloudformation:stack-name,sparta-role,Name" $ssh_user_arg $ssh_key_arg | tee "$tgt"
echo "Done."

