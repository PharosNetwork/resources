# Aldaba OPS

Aldaba OPS 是 Aldaba2.x 专用的 部署 & 运维 工具。

需求 & 架构 文档：
https://yuque.antfin-inc.com/antchain/aldaba-ng/yg0eq5

详细设计文档：
https://yuque.antfin-inc.com/antchain/aldaba-ng/xze5r50mgdgs9ifq

## 规范指南

### Python 开发规约

https://developer.alipay.com/article/8905

### 关于《Python 开发规约》的思考

https://developer.alipay.com/article/8759

### Python 规范指南

https://yuque.antfin.com/lj220859/ohrkfd/aplfo0

### 蚂蚁统一制品库用户手册v1.0

https://yuque.antfin.com/antbuild/bpxc9y/aww0ho?

### pipenv 官方文档

https://pipenv.pypa.io/en/latest/

### fabric 官方文档

https://docs.fabfile.org/en/stable/

### click 官方文档

https://click.palletsprojects.com/en/8.1.x/

### marshmallow 官方文档

https://marshmallow.readthedocs.io/en/stable/

## 环境准备

### step1 安装 pipenv

    pip3 install --user pipenv==11.10.4

### step2 指定某一Python版本创建虚拟环境

    pipenv --python 3.6

### step3 下载依赖(*可以省略，安装 & 打包的时候再下载依赖)

    pipenv install

## 安装 & 打包

> 安装 的目的是为了本地可以使用 `aldaba-ops` 命令，详情见 《Click 官方文档》

> 打包 的目的是将工具上传到内部 pip 源，其他机器可以直接 pip install aldaba-ops 下载安装工具

### 编辑模式（开发调试用）

    pipenv run pip install -e .

### 本地模式（脚本用）

    pipenv run pip install .

### 上传到内部源（禁止非管理员操作）

```
// 打包
python setup.py sdist
// 安装 twine
pip3 install twine 
// 上传前检查(替换版本)
twine check dist/aldaba_ops-0.0.1.tar.gz dist/$aldaba_ops-0.0.1.whl  
// 上传
twine upload -r aldaba_ops dist/*
```

## 使用

```
   Usage: aldaba-ops [OPTIONS] COMMAND [ARGS]...
   
   Options:
   --debug / --no-debug Debug mode
   --version Show the version and exit.
   --help Show this message and exit.
   
   Commands:
   bootstrap Clean, genesis and setmeta with $domain_label.json
   clean Clean data, logs and bin/stdout with $domain_label.json
   configure Generate $domain_label.json and update svc env.json
   deploy Deploy with $domain_label.json
   restart Stop then start with $domain_label.json
   start Start with $domain_label.json
   status Status with $domain_label.json
   stop Stop with $domain_label.json
```

### 配置生成

```
   Usage: aldaba-ops configure [OPTIONS] [DEPLOY_CONF_PATH]
   
      Generate $domain_label.json and update svc env.json
   
   Options:
     --svc_mng_dir TEXT  Svc shells run root
     --help              Show this message and exit.
   
   Example:
   
   aldaba-ops configure
   aldaba-ops configure deploy.json
   aldaba-ops configure --svc_mng_dir deploy.json
```

### 部署

```
   Usage: aldaba-ops deploy [OPTIONS] [DOMAIN_COMPOSE_PATH]
   
     Deploy with $domain_label.json
   
   Options:
     -s, --service TEXT  multiple option [all|aldaba|svc|service_cluster(like
                         portal, storage)|only_aldaba_instance(like portal0)]
     --help              Show this message and exit.
   
   Example:
   aldaba-ops deploy
   aldaba-ops deploy domain0.json
   aldaba-ops deploy -s all domain0.json
   aldaba-ops deploy -s svc -s aldaba domain0.json
   aldaba-ops deploy -s portal0 -s portal1 domain0.json
```

### 清理

```
   Usage: aldaba-ops clean [OPTIONS] [DOMAIN_COMPOSE_PATH]
   
     Clean data, logs and bin/stdout with $domain_label.json
   
   Options:
     -s, --service TEXT  multiple option [all|aldaba|svc|service_cluster(like
                         portal, storage)|only_aldaba_instance(like portal0)]
     --help              Show this message and exit.
   
   Example:
   aldaba-ops clean
   aldaba-ops clean domain0.json
   aldaba-ops clean -s all domain0.json
   aldaba-ops clean -s svc -s aldaba domain0.json
   aldaba-ops clean -s portal0 -s portal1 domain0.json
```

### 初始化（清理+创世+setmeta）

```
   Usage: aldaba-ops bootstrap [OPTIONS] [DOMAIN_COMPOSE_PATH]
   
     Clean, genesis and setmeta with $domain_label.json
   
   Options:
     -s, --service TEXT  multiple option [all|aldaba|svc]
     --help              Show this message and exit.
   
   Example:
   aldaba-ops bootstrap
   aldaba-ops bootstrap domain0.json
   aldaba-ops bootstrap -s all domain0.json
   aldaba-ops bootstrap -s svc -s aldaba domain0.json
```

### 启动

```
   Usage: aldaba-ops start [OPTIONS] [DOMAIN_COMPOSE_PATH]
   
     Start with $domain_label.json
   
   Options:
     -s, --service TEXT  multiple option [all|aldaba|svc|service_cluster(like
                         portal, storage)|only_aldaba_instance(like portal0)]
     --help              Show this message and exit.
   
   Example:
   aldaba-ops start
   aldaba-ops start domain0.json
   aldaba-ops start -s all domain0.json
   aldaba-ops start -s svc -s aldaba domain0.json
   aldaba-ops start -s portal0 -s portal1 domain0.json
```

### 重新启动（先关闭再启动）

```
   Usage: aldaba-ops restart [OPTIONS] [DOMAIN_COMPOSE_PATH]
   
     Stop then start with $domain_label.json
   
   Options:
     -s, --service TEXT  multiple option [all|aldaba|svc|service_cluster(like
                         portal, storage)|only_aldaba_instance(like portal0)]
     --help              Show this message and exit.
   
   Example:
   aldaba-ops restart
   aldaba-ops restart domain0.json
   aldaba-ops restart -s all domain0.json
   aldaba-ops restart -s svc -s aldaba domain0.json
   aldaba-ops restart -s portal0 -s portal1 domain0.json
```

### 停止

```
   Usage: aldaba-ops stop [OPTIONS] [DOMAIN_COMPOSE_PATH]
   
     Stop with $domain_label.json
   
   Options:
     -s, --service TEXT  multiple option [all|aldaba|svc|service_cluster(like
                         portal, storage)|only_aldaba_instance(like portal0)]
     --help              Show this message and exit.
   
   Example:
   aldaba-ops stop
   aldaba-ops stop domain0.json
   aldaba-ops stop -s all domain0.json
   aldaba-ops stop -s svc -s aldaba domain0.json
   aldaba-ops stop -s portal0 -s portal1 domain0.json
```

### 查看状态

```
   Usage: aldaba-ops status [OPTIONS] [DOMAIN_COMPOSE_PATH]
   
     Status with $domain_label.json
   
   Options:
     -s, --service TEXT  multiple option [all|aldaba|svc|service_cluster(like
                         portal, storage)|only_aldaba_instance(like portal0)]
     --help              Show this message and exit.
   
   Example:
   aldaba-ops status
   aldaba-ops status domain0.json
   aldaba-ops status -s all domain0.json
   aldaba-ops status -s svc -s aldaba domain0.json
   aldaba-ops status -s portal0 -s portal1 domain0.json
```

## QA

1. pip 使用镜像提升下载速度，例如:

    ```
    // 公网 阿里云 镜像源
    pip3 install --user pipenv==11.10.4 -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
    
    // 内网 蚂蚁 镜像源
    pip3 install --user pipenv==11.10.4 -i https://pypi.antfin-inc.com/simple antflux --trusted-host pypi.antfin-inc.com
    ```

2. pipenv 是安装在用户目录下 ，一般为：~/.local/bin/pipenv，注意替换

3. pipenv 有两种使用方式。一般调试用第一种，脚本用第二种。如下：

    ```
    // 第一种：激活虚拟环境
    pipenv shell
    [COMMAND1]
    [COMMAND2]
    ...
    exit
    
    // 第二种：执行命令时指定
    pipenv run [COMMAND1]
    pipenv run [COMMAND2]
    ...
    ```