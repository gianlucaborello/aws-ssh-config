import argparse
import re
import sys
import boto.ec2
import os


AMIS_TO_USER = {
    'amzn' : 'ec2-user',
    'ubuntu' : 'ubuntu',
    'CentOS' : 'root',
    'DataStax' : 'ubuntu',
    'CoreOS' : 'core'
}

BLACKLISTED_REGIONS = [
    'cn-north-1',
    'us-gov-west-1'
]


def doesKeyFileExist(name, extension='pem'):
    keyFile = os.path.expanduser("~") + '/.ssh/' + name + '.' + extension
    return os.path.isfile(keyFile) and os.access(keyFile, os.R_OK)

def generate_id(instance, tags_filter, region):
    id = ''

    if tags_filter is not None:
        for tag in tags_filter.split(','):
            value = instance.tags.get(tag, None)
            if value:
                if not id:
                    id = value
                else:
                    id += '-' + value
    else:
        for tag, value in instance.tags.iteritems():
            if not tag.startswith('aws'):
                if not id:
                    id = value
                else:
                    id += '-' + value

    if not id:
        id = instance.id

    if region:
        id += '-' + instance.placement

    return id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tags', help='A comma-separated list of tag names to be considered for concatenation. If omitted, all tags will be used')
    parser.add_argument('--region', action='store_true', help='Append the region name at the end of the concatenation')
    parser.add_argument('--private', action='store_true', help='Use private IP addresses (public are used by default)')
    parser.add_argument('--profile', help='specify aws credential profile to use')
    parser.add_argument('--user', help='override the ssh username for all hosts')
    parser.add_argument('--default-user', help='default ssh username to use if we cannot detect from AMI name')
    parser.add_argument('--prefix', default='', help='specify a prefix to prepend to all host names')

    args = parser.parse_args()

    instances = {}
    counts_total = {}
    counts_incremental = {}
    amis = {}

    for region in boto.ec2.regions():
        if region.name in BLACKLISTED_REGIONS:
            continue
        if args.profile:
            conn = boto.ec2.connect_to_region(region.name, profile_name=args.profile)
        else:
            conn = boto.ec2.connect_to_region(region.name)

        for instance in conn.get_only_instances():
            if instance.state != 'running':
                continue

            if instance.platform == 'windows':
                continue

            if instance.key_name is None:
                continue

            if instance.launch_time not in instances:
                instances[instance.launch_time] = []

            instances[instance.launch_time].append(instance)

            id = generate_id(instance, args.tags, args.region)

            if id not in counts_total:
                counts_total[id] = 0
                counts_incremental[id] = 0

            counts_total[id] += 1

            if args.user:
                amis[instance.image_id] = args.user
            else:
                if not instance.image_id in amis:
                    image = conn.get_image(instance.image_id)

                    for ami, user in AMIS_TO_USER.iteritems():
                        regexp = re.compile(ami)
                        if image and regexp.match(image.name):
                            amis[instance.image_id] = user
                            break

                    if instance.image_id not in amis:
                        amis[instance.image_id] = args.default_user
                        if args.default_user is None:
                            image_label = image.name if image is not None else instance.image_id
                            sys.stderr.write('Can\'t lookup user for AMI \'' + image_label + '\', add a rule to the script\n')

    for k in sorted(instances):
        for instance in instances[k]:
            if args.private:
                if instance.private_ip_address:
                    ip = instance.private_ip_address
            else:
                if instance.ip_address:
                    ip = instance.ip_address
                elif instance.private_ip_address:
                    ip = instance.private_ip_address
                else:
                    sys.stderr.write('Cannot lookup ip address for instance %s, skipped it.' % instance.id)
                    continue

            id = generate_id(instance, args.tags, args.region)

            if counts_total[id] != 1:
                counts_incremental[id] += 1
                id += '-' + str(counts_incremental[id])

            print 'Host ' + args.prefix + id
            print '    HostName ' + ip

            try:
                if amis[instance.image_id] is not None:
                    print '    User ' + amis[instance.image_id]
            except:
                pass

            if doesKeyFileExist(instance.key_name):
                print '    IdentityFile ~/.ssh/' + instance.key_name + '.pem'
            print '    StrictHostKeyChecking no' # just for me, removing this is usually a good choice
            print


if __name__ == '__main__':
    main()
