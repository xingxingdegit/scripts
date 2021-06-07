#!/bin/bash
#
# deploy_oss.sh <deploy|rollback> <OSS_Bucket> <cp|sync> <JOB_NAME>

if [ $# -ne 4 ];then
    echo "argv num is error"
    echo "<deploy|rollback> <cp|sync> <oss-name> <job-name>"
    exit 3
fi

# 执行的操作，部署or回滚
operation=$1

# 上传oss的方式, sync or cp
upload_type=$2

# 上传到哪个oss bucket
oss_bucket=$3

# 编译的job名称, 用于找到编译以后的文件。后边可以改成通过jenkins $JOB变量提取的
job_name=$4

# jenkins_home, 用于找到编译以后的文件。
jenkins_home=/home/www/.jenkins

# 存储每次编译的文件，一方面用于这一次文件上传, 另一方面用于回滚操作
jobs_home=/home/www/deploy_oss/jobs_home
mkdir -p $jobs_home
cd $jobs_home

# ossutil命令, 需要提前初始化话ossutil的配置文件。
ossutil="/usr/local/bin/ossutil64 --config-file ~/.ossutilconfig"

PATH=/data/jdk/bin:/data/jdk/jre/bin:/data/maven/bin:/data/node/bin:/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin:/data/yarn-v1.10.1/bin:/root/bin

datetime=`date '+%Y%m%d%H%M%S'`
if [ -d $datetime ];then
    sleep 1
    datetime=`date '+%Y%m%d%H%M%S'`
fi

# 脚本默认返回码,防止部署有问题，但是返回了0
return_code=5

# 为了精简jenkins传递的变量，就写这里了，如果各个项目有不同的文件，再做修改。
set_meta_file=/index.html

# 
function set_meta_oss {
    echo "filename: $set_meta_file"
    ossutil64 set-meta oss://ops-mytest$set_meta_file Cache-Control:"no-cache;no-store" --update
    return $?
}

# 
function upload_oss {
    upload_dir=$1
    if [ $upload_type == 'cp' ];then
        $ossutil cp -f -r $upload_dir oss://$oss_bucket
        if [ $? -ne 0 ];then
            rm -rf $upload_dir
            return 2
        fi
            
    elif [ $upload_type == 'sync' ];then
        $ossutil sync --delete -f $upload_dir oss://$oss_bucket
        if [ $? -ne 0 ];then
            rm -rf $upload_dir
            return 2
        fi
    else
        echo "upload_type is error"
        return 3
    fi
}


function deploy {
    src_tar_path=$jenkins_home/workspace/$job_name/${job_name}.tar
    dest_path=$job_name/$datetime
    mkdir -p $dest_path && \
    cd $job_name && \
    tar -xf $src_tar_path -C $datetime
    if [ $? -ne 0 ];then
        rm -rf $datetime
        return 1
    fi
    upload_oss $datetime
    return $?
}

function rollback {
    dest_path=$job_name/$datetime
    cd $job_name
    if [ $? -ne 0 ];then
        return 2
    fi
    # 确认有可供回滚的目录
    num=`ls | grep -E '[0-9]{14}' | wc -l`
    if [ $num -lt 2 ];then
        echo "not enough directory to rollback"
        return 1
    fi
    # 删除最新的目录，然后把剩下的最新的目录上传
    rm -rf `ls -r | grep -E '[0-9]{14}' | head -n 1` && \
    rollback_dir=`ls -r | grep -E '[0-9]{14}' | head -n 1`
    if [ $? -ne 0 ];then
        return 3
    fi
    echo "生效目录: $rollback_dir"
    upload_oss $rollback_dir
    return $?
}

# 部署以及回滚
case $operation in
    deploy)
        echo "开始部署新版本"
        deploy
        return_code=$?
        if [ $return_code -eq 0 ];then
            echo "----------------------"
            echo "部署成功"
            echo "----------------------"
        else
            echo "----------------------"
            echo "部署失败"
            echo "----------------------"
        fi
        ;;
    rollback)
        echo "开始回滚老版本"
        rollback
        return_code=$?
        if [ $return_code -eq 0 ];then
            echo "----------------------"
            echo "回滚成功"
            echo "----------------------"
        else
            echo "----------------------"
            echo "回滚失败"
            echo "----------------------"
        fi
        ;;
    *)
        echo "$1 is not <deploy|rollback"
        return_code=4
esac

# 设置文件响应的http头部信息，主要就是设置某些文件不能缓存。
echo "开始设置文件元信息"
set_meta_oss
meta_code=$?
return_code=$[$return_code+$meta_code]

if [ $meta_code -eq 0 ];then
    echo "----------------------"
    echo "设置文件元信息成功"
    echo "----------------------"
else
    echo "----------------------"
    echo "设置文件元信息失败"
    echo "----------------------"
fi

exit $return_code

