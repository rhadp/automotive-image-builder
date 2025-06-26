<!-- markdownlint-disable-file MD013 -->

# automotive-image-builder integration tests

## Installation

The integration tests use [tmt](https://tmt.readthedocs.io/en/stable/) framework to manage and run integration tests.

### Installing packages using RPM (Fedora / CentOS Stream)

```shell
dnf install \
    tmt-all \
    virt-install \
    -y
```

## Running integration tests

### Using local machine

```shell
dnf install \
    tmt-all \
    virt-install \
    git-gui \
    -y
```
Using this method tests will run on your local machine, where you need to have install all automotive-image-builder
dependencies and also tmt infrastructure (more details in the relevant section below).

To run integration tests please execute below command in the [tests](./) directory:

#### Running Tests Requiring sudo Privileges
Some integration tests require sudo permissions.
There are two ways to provide these permissions in a non-interactive environment:
1. Using SUDO_ASKPASS
You can use the SUDO_ASKPASS environment variable to provide a script that returns your sudo password.

```shell
cd tests
SUDO_ASKPASS=/usr/libexec/git-core/git-gui--askpass tmt --feeling-safe run -v
 -ePROJECT_DIR="Absolute path to your repository clone" plan --name local
```

2. Allow Password-less sudo for Specific Commands
You can configure sudo to run specific commands without asking for a password.
See the Fedora guide for setup:
https://docs.fedoraproject.org/en-US/quick-docs/performing-administration-tasks-using-sudo/


### Using manually provisioned machine or VM

Using this method requires manual provisioning of a machine or a VM before running tests with following requirements:

- IP or a hostname of the machine/VM needs to be knowns
- SSH key authentication need to be set up to access this machine/VM

To run integrations tests inside this machine/VM please execute following commands:

```shell
cd tests
tmt run -v -eNODE="IP or hostname" plan --name connect
```

### Using manually provisioned machine or VM with custom a-i-b package

To use custom a-i-b package source RPM needs to be uploaded to testing machine before executing tests, for example:

```shell
make srpm
scp -i ~/.ssh/aib-tests automotive-image-builder*.src.rpm root@"IP or hostname":/var/tmp/aib-srpm
```

To run integrations tests inside this machine/VM with custom a-i-b build please execute following commands:

```shell
cd tests
tmt run -v -eNODE="IP or hostname" -eBUILD_AIB_RPM=yes plan --name connect
```

### Customizing test execution

Following environment variable exists to customize test execution:

- **`AIB_BASE_REPO`**
   - Contains the URL of the base repository to install automotive-image-builder and its dependencies from
   - Default value: `https://autosd.sig.centos.org/AutoSD-9/nightly/repos/AutoSD/compose/AutoSD/\$arch/os/`
- **`AIB_CUSTOM_REPO`**
   - Contains the URL of the custom repository to install automotive-image-builder and its dependencies from
     (for example to test custom automotive-image-builder package)
   - Default value: _empty_
- **`AIB_SRPM_DIR`**
   - Directory where a-i-b source RPM should be uploaded before tests execution
   - Default value: `/var/tmp/aib-srpm`
- **`BUILD_AIB_RPM`**
   - Enable/disable building a-i-b package from source RPM package provided on a machine specified by `NODE` environment
     variable
   - Default value: `no`
   - Possible values: `yes` `no`
- **`NODE`**
   - IP address or hostname of machine or VM, where integration tests will be run
   - Default value: _empty_
- **`NODE_SSH_KEY`**
   - Path to the SSH key use to connect to testing machine or VM
   - Default value: `~/.ssh/aib-tests`

## Setting up your machine to run tests locally

Following packages needs to be installed on your machine to be able to run tests locally:

```shell
# Install automotive-image-builder dependencies
dnf install \
    android-tools \
    osbuild \
    osbuild-auto \
    osbuild-luks2 \
    osbuild-lvm2 \
    osbuild-ostree \
    ostree \
    python3-jsonschema \
    python3-pyyaml

# Install testing infrastructure
dnf install tmt-all
```

## Setting up a VM to run integration tests

Following sections provides detailed guide to prepare a VM to run integration tests agains on your local machine.

### Generating SSH keys to access the VM

Following command will create SSH key pair in the `~/.ssh` directory, which later will be used to access VM, where
tests will be executed:

```shell
cd ~/.ssh
ssh-keygen -t ecdsa -f aib-tests -N "" -C "root@aib-tests"
```

### Preparing cloud-init configuration file

VM, where tests will be executed, will be configured using following cloud-init user data file:

```yaml
#cloud-config

users:
  - name: root
    ssh_authorized_keys:
      - <PUBLIC SSH KEY>

ssh:
  disable_root: false

yum_repos:
  aib-base-repo:
    name: AIB Base Repository
    baseurl: https://autosd.sig.centos.org/AutoSD-9/nightly/repos/AutoSD/compose/AutoSD/${arch}/os/
    enabled: true
    gpgcheck: false


# preinstall automotive-image-builder dependencies
packages:
  - android-tools
  - osbuild
  - osbuild-auto
  - osbuild-luks2
  - osbuild-lvm2
  - osbuild-ostree
  - ostree
  - python3-jsonschema
  - python3-pyyaml

power_state:
  delay: now
  mode: poweroff
  message: Powering off a-i-b testing VM
  timeout: 2
  condition: true
```

Please save above content into `/tmp/user-data.yml` and replace `<PUBLIC SSH KEY`> with the content of
`~/.ssh/aib-tests.pub` file created in the previous section.


### Creating the VM

CentOS Stream base image casn be downloaded using following command:

```shell
sudo curl -o /var/lib/libvirt/images/aib-tests.qcow2 \
    https://cloud.centos.org/centos/9-stream/x86_64/images/CentOS-Stream-GenericCloud-x86_64-9-latest.x86_64.qcow2
```

And then let's create VM:

```shell
cd tests
sudo virt-install  \
     --name aib-tests \
     --memory 16384  --cpu host-model --vcpus 4 --graphics none \
     --os-variant centos-stream9 \
     --import \
     --disk /var/lib/libvirt/images/aib-tests.qcow2,format=qcow2,bus=virtio \
     --network default  \
     --cloud-init disable=on,user-data=/tmp/user-data.yml \
     --noreboot
```

The VM should be created and it should be stopped once creation is finished.

To save the of the disk of the VM for reuse after test execution please run following command

```shell
sudo qemu-img convert -c -O qcow2 \
    /var/lib/libvirt/images/aib-tests.qcow2 \
    /var/lib/libvirt/images/aib-tests.qcow2.bck
```

When done let's start the VM using:

```shell
sudo virsh start aib-tests
```

And let's display VM IP address, which will be needed for test execution:

```shell
sudo virsh domifaddr aib-tests
```

VM can be accessed using following command:

```shell
ssh -i ~/.ssh/aib-tests root@<VM IP ADDRESS>
```


### Staring up the VM before running integration tests

1. Make sure the VM is stopped

   ```shell
   sudo virsh shutdown aib-tests
   ```

2. Use preconfigure disk for the VM

   ```shell
   sudo cp /var/lib/libvirt/images/aib-tests.qcow2.bck \
       /var/lib/libvirt/images/aib-tests.qcow2
   ```

3. Start the VM

   ```shell
   sudo virsh start aib-tests
   ```


## Developing integration tests

### Generating test ID

Every test should be distinctly identified with a unique ID. Therefore, when adding a new test, please execute the following command to assign an ID to the new test:

```shell
$ cd tests
$ tmt test id .
New id 'UUID' added to test '/tests/path_to_your_new_test'.
...
```

### Checking for duplicate test IDs and summaries

In addition to having a unique ID, the summaries of tests should be descriptive and unique as well. The CI will perform appropriate linting. This can also be invoked locally:

```shell
$ cd tests

# requires tmt >= 1.35
$ tmt lint tests
Lint checks on all
fail G001 duplicate id "96aa0e17-5e23-4cc3-bc34-88368b8cc07b" in "/tests/some-test"
fail G001 duplicate id "96aa0e17-5e23-4cc3-bc34-88368b8cc07b" in "/tests/another-test"
```
