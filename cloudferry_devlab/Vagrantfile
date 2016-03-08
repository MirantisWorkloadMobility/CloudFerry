# -*- mode: ruby -*-
# vi: set ft=ruby ts=2 sw=2 et sua= inex= :

config_file = File.join(File.dirname(__FILE__), "/config.ini")
options = {}
File.foreach(config_file) { |line|
  option, value = line.split("=")
  option = option.strip()
  if !value.nil?
    value = value.strip()
    options[option] = value
  end
}

nodes = {
  "grizzly" => {
    "box" => "openstack-user/precise-grizzly",
    "ip" => "#{options['grizzly_ip']}",
    "ip2" => "#{options['grizzly_ip2']}",
    "memory" => 4096,
    "role" => "openstack"
  },
  "icehouse" => {
    "box" => "openstack-user/trusty-icehouse",
    "ip" => "#{options['icehouse_ip']}",
    "ip2" => "#{options['icehouse_ip2']}",
    "memory" => 4096,
    "role" => "openstack"
  },
  "juno" => {
    "box" => "openstack-user/trusty-juno",
    "ip" => "#{options['juno_ip']}",
    "ip2" => "#{options['juno_ip2']}",
    "memory" => 4096,
    "role" => "openstack"
  },
  "cloudferry" => {
    "box" => "hashicorp/precise64",
    "ip" => "#{options['cloudferry_ip']}",
    "ip2" => "#{options['cloudferry_ip2']}",
    "memory" => 2048,
    "role" => "lab"
  },
  "nfs" => {
    "box" => "openstack-user/nfs-server",
    "ip" => "#{options['nfs_ip']}",
    "ip2" => "#{options['nfs_ip2']}",
    "memory" => 1024,
    "cpus" => 1
  }
}

options['http_proxy'] ||= ""
options['https_proxy'] ||= ""
options['ftp_proxy'] ||= ""

Vagrant.require_version '>= 1.6.0'

if not options['http_proxy'].empty?
    unless Vagrant.has_plugin?("vagrant-proxyconf")
        system('vagrant plugin install vagrant-proxyconf')
    end
end

Vagrant.configure(2) do |config|

  if Vagrant.has_plugin?("vagrant-proxyconf")
    config.proxy.http     = "#{options['http_proxy']}"
    config.proxy.https    = "#{options['https_proxy']}"
    config.proxy.ftp      = "#{options['ftp_proxy']}"
    config.proxy.no_proxy = "localhost,127.0.0.1,"\
                            "#{options['grizzly_ip']},"\
                            "#{options['icehouse_ip']},"\
                            "#{options['juno_ip']},"\
                            "#{options['cloudferry_ip']},"\
                            "#{options['nfs_ip']}"
  end

  config.vm.provision "shell", path: "./provision/prerequisites.sh"
  etc_hosts = nodes.map { |name, data| [data["ip"], name].join(' ') }.join("\n")

  nodes.each do |nodename, nodedata|
    config.vm.define nodename do |thisnode|
      thisnode.vm.box = nodedata['box']
      thisnode.vm.hostname = nodename
      thisnode.vm.provision "shell", inline: "echo '#{etc_hosts}' >> /etc/hosts"
      thisnode.vm.provision "shell",
        path: "./provision/keys.sh",
        args: [ "--public-key", File.read("#{ENV["HOME"]}/#{options['public_key_path']}").strip() ]

      case nodedata.fetch("role", "")
        when "openstack"
          thisnode.vm.provision "shell", path: "./provision/fix_interfaces.sh"
          thisnode.vm.provision "shell", path: "./provision/create_disks_swift.sh"
          if nodename == "grizzly" then
            thisnode.vm.provision "shell", path: "./provision/qemu.sh"
          elsif nodename == "icehouse" then
            thisnode.vm.provision "shell", path: "./provision/cleanup_nova_instances.sh"
          end
          thisnode.vm.provision "shell", path: "./provision/libvirt.sh"
        when "lab"
          thisnode.vm.provision "shell",
            path: "./provision/cloudferry.sh"
          if File.exist?(File.join(Dir.home, ".ssh/id_rsa")) then
            thisnode.vm.provision "file",
              source: "~/.ssh/id_rsa",
              destination: "/home/vagrant/.ssh/id_rsa"
          end
      end

      thisnode.vm.network "private_network", ip: nodedata['ip']
      thisnode.vm.network "private_network", ip: nodedata['ip2']

      thisnode.vm.provider "virtualbox" do |v|
        v.memory = nodedata.fetch("memory", 1024)
        v.cpus = nodedata.fetch("cpus", 2)
        v.customize ["modifyvm", :id, "--nicpromisc2", "allow-all"]
      end
    end
  end
end
