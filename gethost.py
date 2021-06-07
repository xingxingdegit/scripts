#

import os
import subprocess
import re
import traceback
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

re_pattern = r'^LISTEN +[0-9]+ +[0-9]+ +\*:([0-9]+) +\*:\* +users:\(\("java",pid=([0-9]+),fd=[0-9]+\)\)'

re_compile = re.compile(re_pattern)

# 项目都是带 -production的那种，因为要从config.xml里获取主机地址。
# 目录下是各个项目的目录，项目目录下是config.xml配置文件。 跟jenkins下的jobs一样。
jobsdir = '/home/jobs'
# 要采集信息的项目名称， 需要是带 -production的那种名称。
jobname_file = '/home/jobnames'

# 最终输出配置到这个文件
conf_file = '/home/jar_port.ini'
# 获取失败的服务，记录进这个文件
jump_job_file = '/home/jump_job.txt'

jobnames = []
with open(jobname_file, 'r') as fd:
    for name in fd:
        jobnames.append(name.strip())


def get_host(config_file):
    xml_tree = tree = ET.ElementTree(file=config_file)
    element_root = xml_tree.getroot()
    element_properties = element_root.find('properties')
    element_property = element_properties.find('hudson.model.ParametersDefinitionProperty')
    element_parameter_definitions = element_property.find('parameterDefinitions')
    element_choice_definition = element_parameter_definitions.findall('hudson.model.ChoiceParameterDefinition')
    #print(element_choice_definition)
    for choice_define in element_choice_definition:
        choice_name = choice_define.find('name')
        if choice_name.text != 'host':
            continue

        choice_params_list = choice_define.find('choices')
        choice_a = choice_params_list.find('a')
        element_host = choice_a.find('string')
        #print(element_host)
        host = element_host.text
        host = host.split(',')[0].strip()
        if host:
            print('+++++++success')
            print(host)
            return host
        else:
            print('host is {}'.format(host))
            print('+++++++failed')
            return False
              

def get_port(host):
    command = 'ansible {} -u www -i ~/hosts --private-key=~/.ssh/id_rsa -b -m shell -a "ss -tnlp | grep [j]ava"'.format(host)
    data = subprocess.check_output(command, shell=True)
#    print(data)
    pids = set()
    ports = []
    for line in data.split('\n'):
        if not line.strip():
            continue
        if host in line:
            continue
        if '127.0.0.1' in line:
            continue
        re_object = re_compile.match(line)
        if re_object:
            #print(re_object.group())
            ports.append(re_object.group(1))
            pids.add(re_object.group(2))
        else:
            print('host:{}|data:{}|not match'.format(host, line))
            print('+++++++failed')
            return False
    if len(pids) == 0:
        print('host:{}|count num of pid  = 0'.format(host))
        print('+++++++failed')
        return False
    if len(pids) > 1:
        print('host:{}|pids:{}|count num of pid  > 1'.format(host, pids))
        print('+++++++failed')
        return False
    print('+++++++success')
    print(ports, host)
    return ports

def wait_for_test(host, port):
    command = 'ansible {} -u www -i ~/hosts --private-key=~/.ssh/id_rsa -b -m wait_for -a "port={} state=started timeout=20"'.format(host, port)
#    data = subprocess.check_output(command, shell=True)
    data = subprocess.call(command, shell=True)
    if data==0:
        print('+++++++success')
        return True
    else:
        print('+++++++failed')
        return False

def write_conf(project, port):
    try:
        with open(conf_file, 'a') as fd:
            fd.write('''
#It was written in here by script
if [ "$PROJECT" == "{}" ];then
    jar_port={}
fi
'''.format(project, port))
    except Exception:
        traceback.print_exc()
        print('+++++++failed')
        return False
    print('+++++++success')
    print(project, port)
    return True


for jobname in jobnames:
    print('')
    print('**********************************{}*********************************'.format(jobname))
    print('')
    conf_path = os.path.join(jobsdir, jobname, 'config.xml')
    print('---------------get_hostname------------------')
    hostname = get_host(conf_path)
    if not hostname:
        print('{} is jumped'.format(jobname))
        with open(jump_job_file, 'a') as fd:
            fd.write('{}\n'.format(jobname))
        continue
    print('')
    print('')
    print('---------------get_port------------------')
    port = get_port(hostname)
    if not port:
        print('{} is jumped'.format(jobname))
        with open(jump_job_file, 'a') as fd:
            fd.write('{}\n'.format(jobname))
        continue
    jobname_without_production_list = jobname.split('-')[:-1]
    jobname_without_production = '-'.join(jobname_without_production_list)

    print('')
    print('')
    print('---------------wait_for_test------------------')
    wait_for_state = wait_for_test(jobname_without_production, port[0])
    if wait_for_state:
        print('')
        print('')
        print('---------------write to config------------------')
        state = write_conf(jobname_without_production, port[0])
        if state:
            print('{} write to config success'.format(jobname))
        else:
            print('{} is jumped'.format(jobname))
            with open(jump_job_file, 'a') as fd:
                fd.write('{}\n'.format(jobname))
            print('{} write to config failed'.format(jobname))
        continue
    else:
        print('{} is jumped'.format(jobname))
        with open(jump_job_file, 'a') as fd:
            fd.write('{}\n'.format(jobname))
        continue
        print('job:{}|wait for test is failed'.format(jobname))
        








