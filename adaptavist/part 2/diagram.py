from diagrams import Cluster, Diagram, Edge
from diagrams.custom import Custom
from diagrams.alibabacloud.compute import ESS, ECS, ContainerService, ElasticSearch, ContainerRegistry
from diagrams.alibabacloud.network import SLB
from diagrams.alibabacloud.storage import NAS
from diagrams.alibabacloud.application import SLS
from diagrams.alibabacloud.database import ApsaradbPolardb, ApsaradbHbase, ApsaradbRedis
from diagrams.alibabacloud.analytics import AnalyticDb
from diagrams.alibabacloud.web import Dns
from diagrams.alibabacloud.security import AntiDdosPro
from diagrams.k8s.compute import Deploy
from diagrams.k8s.controlplane import API
from diagrams.k8s.infra import Node
from diagrams.onprem.network import Istio
from diagrams.onprem.client import Users
from diagrams.onprem.monitoring import Grafana
from diagrams.onprem.identity import Dex
from diagrams.onprem.security import Vault
from diagrams.onprem.vcs import Gitlab
from diagrams.onprem.iac import Atlantis
from diagrams.onprem.gitops import Argocd
from diagrams.onprem.container import K3S
from diagrams.onprem.ci import Jenkins, Gitlabci
from diagrams.onprem.certificates import LetsEncrypt

graph_attr = {
    "layout":"dot",
    "compound":"true",
}

edge_attr = {
    "splines": "spline",
}

with Diagram("Infrastructure Diagram", graph_attr=graph_attr, show=False):
    dns = Dns("dns")
    client = Users("clients")
    services = [ApsaradbPolardb("alicloud polardb"), 
                AnalyticDb("alicloud mysql"), ApsaradbHbase("alicloud hbase"), 
                ApsaradbRedis("alicloud redis"), ElasticSearch("alicloud elasticsearch")]

    with Cluster("On-premises Openstack"):
        k3s = K3S("k3s cluster")

    with Cluster("My projects"):
        antiddos = AntiDdosPro("alicloud antiddos")
        asm = Istio("alicloud service mesh (istio)")
        sls = SLS("log service")
        registry = ContainerRegistry("alicloud container registry")

        with Cluster("api-gateway"):
            with Cluster("Server Load Balancers (layer 4)\n\nSLB's ip whitelist is configured to only forward traffic with antiddos IP to HAProxy"):
                slb = [SLB("slb1"), SLB("slb2"), SLB("slb3")]

            with Cluster("HAProxy (layer 7)\n\n HaProxy performs layer 7 filtering, cert binding and also ip whitelist"):
                haproxy = [ECS("haproxy1"), ECS("haproxy2"), ECS("haproxy3")]
                ess = ESS("auto scaling group")

        with Cluster("Container Service for Kubernetes"):
            nas = NAS("file system")
            lb = SLB("slb")
            with Cluster("Alicloud Kubernetes Cluster"):
                ack = ContainerService("alicloud kubernetes")
            
            with Cluster("Alicloud Kubernetes Cluster in other region/zones"):
                other_lb = SLB("slb")
                other_ack = ContainerService("alicloud kubernetes")

    client >> Edge(label="Return antiddos cname") >> dns
    dns >> Edge(label="Resolve domain") >> client >> antiddos >> slb >> ess
    for hp in haproxy:
        ess - hp
    k3s >> Edge(label="Deployment") >> ack
    haproxy >> asm >> ack
    haproxy >> sls
    asm >> sls
    ack >> registry
    ack >> sls
    ack >> nas
    for svc in services:
        ack >> svc
    ack << Edge(label="grpc service connection") >> lb << Edge(label="") >> other_lb << Edge(label="grpc service connection") >> other_ack

with Diagram("k8s diagram", show=False, graph_attr=edge_attr):

    with Cluster("k3s Cluster"):
        Deploy("Other internal applications")
        auth = Dex("dex-authenticator")
        vault = Vault("hashicorp vault")
        jenkins = Jenkins("jenkins")
        argocd = Argocd("argocd")
        gitlabci = Gitlabci("gitlabci")
        atlantis = Atlantis("atlantis")
        inject = Edge(label="inject Creds")
        atlantis - Edge(label="Integration") - Gitlab("gitlab") - gitlabci
        vault >> inject >> jenkins
        vault >> inject >> auth
        vault >> inject >> gitlabci
        vault >> inject >> argocd
        LetsEncrypt("acme-client") >> Edge(label="Store certs") >> vault
        argocd << Edge(label="trigger") << gitlabci
        vault >> inject >> atlantis
    
    with Cluster("Alicloud Kubernetes Cluster"):
        apiserver = API("kube-apiserver")
        
        with Cluster("Istio Nodepool"):
            Node("worker nodes")
            with Cluster("Istio Namespace"):
                istio = Istio("istio-ingressgateway")

        with Cluster("Monitoring Nodepool"):
            Node("worker nodes")
            with Cluster("Monitoring Namespace"):
                grafana = Grafana("grafana")
                victoriametrics = Custom("victoria-metrics", "./custom-resources/victoria-metrics.png")
                grafana >> victoriametrics

        with Cluster("Primary Nodepool"):
            Node("worker nodes")
            with Cluster("Other Namespaces"):
                [Deploy("addons"),Deploy("built-in kube services")]
            with Cluster("Application Namespace"):
                app1 = Deploy("app1")
                app2 = Deploy("app2")
                app3 = Deploy("app3")
                app1 << Edge(label="") >> app2 << Edge(label="") >> app3
                app = [app1, app2, app3]
            with Cluster("DevOps Namespace"):
                dex = Dex("dex")

    collect = Edge(label="Collect metrics")
    auth - apiserver
    jenkins >> Edge(label="Deploy applications") >> apiserver
    argocd >> Edge(label="Deploy internal applications") >> apiserver
    istio >> dex << collect << victoriametrics
    istio >> app << collect << victoriametrics
    victoriametrics >> istio >> grafana
