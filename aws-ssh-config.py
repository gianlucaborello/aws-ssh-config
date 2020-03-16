#!/usr/bin/env python

import argparse
import re
import sys
import time
import boto3


AMI_NAMES_TO_USER = {
    'amzn': 'ec2-user',
    'ubuntu': 'ubuntu',
    'CentOS': 'root',
    'DataStax': 'ubuntu',
    'CoreOS': 'core'
}

AMI_IDS_TO_USER = {
    'ami-ada2b6c4': 'ubuntu'
}

AMI_IDS_TO_KEY = {
    'ami-ada2b6c4': 'custom_key'
}

BLACKLISTED_REGIONS = [

]


def generate_id(instance, tags_filter, region):
    instance_id = ''

    if tags_filter is not None:
        for tag in tags_filter.split(','):
            for aws_tag in instance['Instances'][0].get('Tags', []):
                if aws_tag['Key'] != tag:
                    continue
                value = aws_tag['Value']
                if value:
                    if not instance_id:
                        instance_id = value
                    else:
                        instance_id += '-' + value
    else:
        for tag in instance['Instances'][0].get('Tags', []):
            if not (tag['Key']).startswith('aws'):
                if not instance_id:
                    instance_id = tag['Value']
                else:
                    instance_id += '-' + tag['Value']

    if not instance_id:
        instance_id = instance['Instances'][0]['InstanceId']

    if region:
        instance_id += '-' + instance[
            'Instances'][0]['Placement']['AvailabilityZone']

    return instance_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--default-user',
        help='Default ssh username to use'
             'if it can\'t be detected from AMI name')
    parser.add_argument(
        '--keydir',
        default='~/.ssh/',
        help='Location of private keys')
    parser.add_argument(
        '--no-identities-only',
        action='store_true',
        help='Do not include IdentitiesOnly=yes in ssh config; may cause'
             ' connection refused if using ssh-agent')
    parser.add_argument(
        '--postfix',
        default='',
        help='Specify a postfix to append to all host names')
    parser.add_argument(
        '--prefix',
        default='',
        help='Specify a prefix to prepend to all host names')
    parser.add_argument(
        '--private',
        action='store_true',
        help='Use private IP addresses (public are used by default)')
    parser.add_argument(
        '--profile',
        help='Specify AWS credential profile to use')
    parser.add_argument(
        '--proxy',
        default='',
        help='Specify a bastion host for ProxyCommand')
    parser.add_argument(
        '--region',
        action='store_true',
        help='Append the region name at the end of the concatenation')
    parser.add_argument(
        '--ssh-key-name',
        default='',
        help='Override the ssh key to use')
    parser.add_argument(
        '--strict-hostkey-checking',
        action='store_true',
        help='Do not include StrictHostKeyChecking=no in ssh config')
    parser.add_argument(
        '--tags',
        help='A comma-separated list of tag names to be considered for'
             ' concatenation. If omitted, all tags will be used')
    parser.add_argument(
        '--user',
        help='Override the ssh username for all hosts')
    parser.add_argument(
        '--white-list-region',
        default='',
        help='Which regions must be included. If omitted, all regions'
             ' are considered',
        nargs='+')
    args = parser.parse_args()

    instances = {}
    counts_total = {}
    counts_incremental = {}
    amis = AMI_IDS_TO_USER.copy()

    print('# Generated on ' + time.asctime(time.localtime(time.time())))
    print('# ' + ' '.join(sys.argv))
    print('# ')
    print('')
    if args.profile:
        session = boto3.Session(profile_name=args.profile)
        regions = session.client('ec2').describe_regions()['Regions']
    else:
        regions = boto3.client('ec2').describe_regions()['Regions']
    for region in regions:
        if (args.white_list_region
                and region['RegionName'] not in args.white_list_region):
            continue
        if region['RegionName'] in BLACKLISTED_REGIONS:
            continue
        if args.profile:
            conn = session.client('ec2', region_name=region['RegionName'])
        else:
            conn = boto3.client('ec2', region_name=region['RegionName'])

        for instance in conn.describe_instances()['Reservations']:
            if instance['Instances'][0]['State']['Name'] != 'running':
                continue

            if instance['Instances'][0].get('KeyName', None) is None:
                continue

            if instance['Instances'][0]['LaunchTime'] not in instances:
                instances[instance['Instances'][0]['LaunchTime']] = []

            instances[instance['Instances'][0]['LaunchTime']].append(instance)

            instance_id = generate_id(instance, args.tags, args.region)

            if instance_id not in counts_total:
                counts_total[instance_id] = 0
                counts_incremental[instance_id] = 0

            counts_total[instance_id] += 1

            if args.user:
                amis[instance['Instances'][0]['ImageId']] = args.user
            else:
                if not instance['Instances'][0]['ImageId'] in amis:
                    image = conn.describe_images(
                        Filters=[
                            {
                                'Name': 'image-id',
                                'Values': [instance['Instances'][0]['ImageId']]
                            }
                        ]
                    )

                    for ami, user in AMI_NAMES_TO_USER.items():
                        regexp = re.compile(ami)
                        if (len(image['Images']) > 0
                                and regexp.match(image['Images'][0]['Name'])):
                            amis[instance['Instances'][0]['ImageId']] = user
                            break

                    if instance['Instances'][0]['ImageId'] not in amis:
                        amis[
                            instance['Instances'][0]['ImageId']
                        ] = args.default_user
                        if args.default_user is None:
                            image_label = image[
                                'Images'
                            ][0][
                                'ImageId'] if len(image['Images']) and image['Images'][0] is not None else instance[
                                        'Instances'][0]['ImageId']
                            sys.stderr.write(
                                'Can\'t lookup user for AMI \''
                                + image_label + '\', add a rule to '
                                'the script\n')

    for k in sorted(instances):
        for instance in instances[k]:
            if args.private:
                if instance['Instances'][0]['PrivateIpAddress']:
                    ip_addr = instance['Instances'][0]['PrivateIpAddress']
            else:
                try:
                    ip_addr = instance['Instances'][0]['PublicIpAddress']
                except KeyError:
                    try:
                        ip_addr = instance['Instances'][0]['PrivateIpAddress']
                    except KeyError:
                        sys.stderr.write(
                            'Cannot lookup ip address for instance %s,'
                            ' skipped it.'
                            % instance['Instances'][0]['InstanceId'])
                        continue

            instance_id = generate_id(instance, args.tags, args.region)

            if counts_total[instance_id] != 1:
                counts_incremental[instance_id] += 1
                instance_id += '-' + str(counts_incremental[instance_id])

            hostid = args.prefix + instance_id + args.postfix
            hostid = hostid.replace(' ', '_')  # get rid of spaces

            if instance['Instances'][0]['InstanceId']:
                print('# id: ' + instance['Instances'][0]['InstanceId'])
            print('Host ' + hostid)
            print('    HostName ' + ip_addr)

            if amis[instance['Instances'][0]['ImageId']] is not None:
                print('    User ' + amis[instance['Instances'][0]['ImageId']])

            if args.keydir:
                keydir = args.keydir
            else:
                keydir = '~/.ssh/'

            if args.ssh_key_name:
                print('    IdentityFile '
                      + keydir + args.ssh_key_name + '.pem')
            else:
                key_name = AMI_IDS_TO_KEY.get(
                    instance['Instances'][0]['ImageId'],
                    instance['Instances'][0]['KeyName'])

                print('    IdentityFile '
                      + keydir + key_name.replace(' ', '_') + '.pem')

            if not args.no_identities_only:
                # ensure ssh-agent keys don't flood
                # when we know the right file to use
                print('    IdentitiesOnly yes')
            if not args.strict_hostkey_checking:
                print('    StrictHostKeyChecking no')
            if args.proxy:
                print('    ProxyCommand ssh ' + args.proxy + ' -W %h:%p')
            print('')


if __name__ == '__main__':
    main()
