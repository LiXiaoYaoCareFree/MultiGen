# 1.使用ubuntu基础镜像来源
FROM ubuntu:22.04

# 2.安装过程避免交互式提示并设置主机名、uv环境目录、uv连接模式
ENV DEBIAN_FRONTEND=noninteractive
ENV HOSTNAME=sandbox
ENV UV_PROJECT_ENVIRONMENT="/venv"
ENV UV_LINK_MODE=copy

# 3.安装基础工具+OpenSSH Server以实现SSH远程环境
# mkdir /var/run/sshd是SSH服务启动必须的目录
RUN apt-get update && apt-get install -y \
    ca-certificates git curl openssh-server\
    && rm -rf /var/lib/apt/lists/* \
    && mkdir /var/run/sshd

# 4.配置SSH的账户密码(开发环境设置root账号密码为root)
RUN echo 'root:root' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# 5.安装uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 6.设置下工作环境
WORKDIR /sandbox

# 7.同步uv环境
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# 8.开放SSH端口(22)和应用端口(8080)
EXPOSE 22 8080

# 9.启动SSH服务(必须使用-D让它在前台运行，否则容器会退出)
CMD ["/usr/sbin/sshd", "-D"]