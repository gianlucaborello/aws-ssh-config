aws-ssh-config
======

Description
---

A very simple script that queries the AWS EC2 API with boto and generates a SSH config file ready to use. 
There are a few similar scripts around but I couldn't find one that would satisfy all my wish list:

- Connect to all regions at once
- Do AMI -> user lookup (regexp-based)
- Support public/private IP addresses (for VPNs and VPCs)
- Support multiple instances with same tags (e.g. autoscaling groups) and provide an incremental count for duplicates based on instance launch time
- Support multiple customizable tags concatenations in a user-provided order
- Support region (with AZ) in the host name concatenation
- Properly leverage tab completion

Usage
---

This assumes boto is installed and configured. Also, private ssh keys must be copied under `~/.ssh/`

Supported arguments:

```
gianluca@sid:~$ python aws-ssh-config.py --help
usage: aws-ssh-config.py [-h] [--tags TAGS] [--private]

optional arguments:
  -h, --help   show this help message and exit
  --tags TAGS  A comma-separated list of tag names to be considered for
               concatenation. If omitted, all tags will be used
  --region     Append the region name at the end of the concatenation
  --private    Use private IP addresses (public are used by default)
```

By default, it will name hosts by concatenating all tags:

```
gianluca@sid:~$ python aws-ssh-config.py > ~/.ssh/config
gianluca@sid:~$ cat ~/.ssh/config
Host dev-worker-1
    HostName 54.173.109.173
    User ec2-user
    IdentityFile ~/.ssh/dev.pem
    StrictHostKeyChecking no

Host dev-worker-2
    HostName 54.173.190.141
    User ec2-user
    IdentityFile ~/.ssh/dev.pem
    StrictHostKeyChecking no

Host prod-worker-1
    HostName 54.164.168.30
    User ec2-user
    IdentityFile ~/.ssh/prod.pem
    StrictHostKeyChecking no

Host prod-worker-2
    HostName 54.174.115.242
    User ubuntu
    IdentityFile ~/.ssh/prod.pem
    StrictHostKeyChecking no
```

ssh completion will immediately work:

```
gianluca@sid:~$ ssh d[TAB]
dev-worker-1
dev-worker-2
```
If the ssh completion will not immediately work you should add the following script to your `.bash_profile`

```
_complete_ssh_hosts ()
{
        COMPREPLY=()
        cur="${COMP_WORDS[COMP_CWORD]}"
        comp_ssh_hosts=`cat ~/.ssh/known_hosts | \
                        cut -f 1 -d ' ' | \
                        sed -e s/,.*//g | \
                        grep -v ^# | \
                        uniq | \
                        grep -v "\[" ;
                cat ~/.ssh/config | \
                        grep "^Host " | \
                        awk '{print $2}'
                `
        COMPREPLY=( $(compgen -W "${comp_ssh_hosts}" -- $cur))
        return 0
}
complete -F _complete_ssh_hosts ssh
```
and run `gianluca@sid:~$ source .bash_profile` 

It's possible to customize which tags one is interested in, as well as the order used for concatenation:

```
gianluca@sid:~$ python aws-ssh-config.py --tags Name > ~/.ssh/config
gianluca@sid:~$ cat ~/.ssh/config
Host worker-1
    HostName 54.173.109.173
    User ec2-user
    IdentityFile ~/.ssh/dev.pem
    StrictHostKeyChecking no

Host worker-2
    HostName 54.173.190.141
    User ec2-user
    IdentityFile ~/.ssh/dev.pem
    StrictHostKeyChecking no

Host worker-3
    HostName 54.164.168.30
    User ec2-user
    IdentityFile ~/.ssh/prod.pem
    StrictHostKeyChecking no

Host worker-4
    HostName 54.174.115.242
    User ubuntu
    IdentityFile ~/.ssh/prod.pem
    StrictHostKeyChecking no

gianluca@sid:~$ python aws-ssh-config.py --tags Name,Infrastructure > ~/.ssh/config
gianluca@sid:~$ cat ~/.ssh/config
Host worker-dev-1
    HostName 54.173.109.173
    User ec2-user
    IdentityFile ~/.ssh/dev.pem
    StrictHostKeyChecking no

Host worker-dev-2
    HostName 54.173.190.141
    User ec2-user
    IdentityFile ~/.ssh/dev.pem
    StrictHostKeyChecking no

Host worker-prod-1
    HostName 54.164.168.30
    User ec2-user
    IdentityFile ~/.ssh/prod.pem
    StrictHostKeyChecking no

Host worker-prod-2
    HostName 54.174.115.242
    User ubuntu
    IdentityFile ~/.ssh/prod.pem
    StrictHostKeyChecking no

```

By default, the ssh user is calculated from a regular expression based on the AMI name. If no matches are found, a warning is printed on standard error and one can edit the script and add the rule to the `AMIS_TO_USER` dictionary:

```
gianluca@sid:~$ python aws-ssh-config.py > ~/.ssh/config
Can't lookup user for AMI 'ubuntu/images/hvm-ssd/ubuntu-trusty-14.04-amd64-server-20140926', add a rule to the script
```

