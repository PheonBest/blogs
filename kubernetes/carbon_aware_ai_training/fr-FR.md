![Cover](https://cdn.hashnode.com/res/hashnode/image/upload/v1757639715283/954a2f5d-131f-49cf-b121-5c47ba620650.png)

Selon le dernier rapport de l'Agence Internationale de l'Énergie (AIE), les datacenters représentaient 1,5 % de la demande mondiale d'électricité en 2024, avec 10 % de cette demande liée à l'intelligence artificielle. L'AIE prévoit que les datacenters atteindront 3 % de la demande mondiale d'électricité, et que 50 % de cette consommation sera due à l'IA, soit une augmentation de 5 à 10 fois par rapport à 2022.

Cette tendance de consommation nous conduit vers une prise de conscience durable : l'importance du carbone dans l'informatique.

L'informatique **carbon-aware** (consciente du carbone) est une approche essentielle pour réduire l'empreinte écologique de nos systèmes informatiques. Le principe est simple mais puissant : **faire plus quand l'électricité est propre et faire moins quand elle est carbonée**. Un kilowattheure n'est pas simplement un kilowattheure - son impact environnemental varie considérablement selon le moment et le lieu de consommation.

Des recherches récentes montrent que l'adoption de stratégies conscientes du carbone peut réduire les émissions de 20 % à 32,9 % [arxiv.org](http://arxiv.org), tout en maintenant ou en améliorant les performances des systèmes. Pour les centres de données et les clusters Kubernetes, cela représente une opportunité majeure.

Atteindre les objectifs de zéro émission nette d’ici 2030 présente d’autres avantages.

* **Réduire les coûts énergétiques** : Exploiter l'énergie lorsque les renouvelables sont abondantes correspond souvent à des périodes où les prix de l'électricité sont plus bas. Le déplacement des charges de travail d'IA pour un seul grand projet peut permettre d'économiser des milliers de mégawattheures. Des pratiques informatiques vertes peuvent entraîner des économies de 20 à 30% sur les dépenses énergétiques.
    
* **Conformité réglementaire** : Les réglementations environnementales devenant plus strictes, ces pratiques aident les organisations à rester en conformité.  
    Depuis 2025 par exemple, les centres de données de plus de 500 kW doivent mesurer et rapporter leur efficacité énergétique **(PUE : Power Usage Effectiveness)**.
    

Dans cet article, nous verrons:

* Les métriques énergétiques pertinentes
    
* Les stratégies carbon-aware basées sur ces métriques
    
* Les modèles d’applications distribuées carbon-aware, avec les outils standard qu’on peut utiliser sur des orchestrateurs comme Kubernetes et Nomad.
    
* Comment implémenter un cluster kubernetes local avec une stratégie carbon-aware.
    
    Les données utilisées proviennent de vessim, un outil qui permet de simuler l’intensité carbone de plusieurs datacenters (microgrid).
    

Je me suis principalement basé sur mon expérience DevOps et ma formation auprès de Pr. Odej Kao, professeur à TU Berlin, et rédacteur avec Philipp Wiesner, Ilja Behnke, Paul Kilian, Marvin Steinke de l’article "[Vessim: A Testbed for Carbon-Aware Applications and Systems." *3rd Workshop on Sustainable Computer Systems (HotCarbon)*.](https://arxiv.org/pdf/2306.09774.pdf) 2024.

## Métriques clés du carbon-aware

Pour implémenter des systèmes conscients du carbone, nous devons d'abord comprendre les concepts fondamentaux qui sous-tendent cette approche.

* **Intensité Carbone (Carbon Intensity - CI)**
    
    L'**intensité carbone** est la mesure de la quantité de carbone (CO2e) émise par kilowattheure (kWh) d'électricité consommée. L'unité standard est le **gCO2eq/kWh**
    
* **Variabilité :** L'intensité carbone n'est pas statique ; elle **varie considérablement selon le lieu et le moment**.
    
    Une région peut avoir un mix énergétique plus propre (par exemple, beaucoup d'hydroélectricité ou de nucléaire), tandis que la même région connaîtra une intensité carbone plus faible lorsque le vent souffle fort ou que le soleil brille, car davantage d'énergie provient de sources renouvelables. C'est sur cette variabilité que nous pouvons agir.
    
* **Intensité Carbone Marginale (Marginal Carbon Intensity) :** Il représente l'intensité carbone de la centrale électrique qui devrait être mise en service pour répondre à toute nouvelle demande d'énergie.
    
    Souvent, ces centrales marginales sont alimentées par des combustibles fossiles. Cependant, dans certains scénarios, l'énergie renouvelable est "curtailed" (rejetée parce qu'il y a un surplus de production). Dans ces situations, toute nouvelle demande peut être satisfaite par cette énergie renouvelable excédentaire, ce qui signifie que l'intensité carbone marginale est de **0 gCO2eq/kWh**
    

## Les stratégies carbon-aware

1. ### **Décalage de la Demande (Demand Shifting)**
    

Le **décalage de la demande** consiste à répondre aux variations de l'intensité carbone en déplaçant l'exécution des charges de travail vers des moments ou des lieux où l'intensité carbone est plus faible. C'est une stratégie clé pour les charges de travail qui ne sont pas ultra-sensibles au temps ou à la localisation.

2. ### **Décalage Spatial (Spatial Shifting)**
    

Nous déplaçons les calculs vers un autre emplacement physique (un autre centre de données, une autre région) où l'intensité carbone est actuellement plus basse. C'est particulièrement efficace pour les **systèmes distribués** qui ont déjà des nœuds dans plusieurs régions, potentiellement alimentées par des réseaux électriques différents

Quelques exemples du spatial shifting:

* **Google Carbon Aware Data Centers** : Google a mis en œuvre des centres de données qui dirigent les charges de travail volumineuses vers les régions et les moments où l'intensité carbone est la plus faible.
    
* **Emerald AI** : Cette startup a réussi à réduire la consommation d'énergie de charges de travail d'IA de 25% lors d'un événement de stress du réseau en redirigeant les charges de travail critiques vers un centre de données dans une région moins stressée
    
    Bien-sûr le déplacement spatial risque d’augmenter la latences pour les utilisateurs ou les transfers de données, et doit toujours respecter les réglementations sur la souveraineté des données
    

**→ Il faut trouver un compromis entre latence, empreinte carbone en restant conforme légalement.**

3. ### **Décalage Temporel (Temporal Shifting)**
    

Nous déplaçons l'exécution des calculs à un autre moment – plus tard dans la journée, la nuit, ou même le week-end – lorsque le soleil est plus présent, le vent souffle plus fort, et que l'intensité carbone est donc plus faible.

Cette approche est idéale pour les **charges de travail par lots (batch workloads) qui ne sont pas sensibles au temps**, telles que la formation de modèles d'apprentissage automatique, l'analyse de données, les sauvegardes ou le rendu vidéo.

* **Mises à jour de Windows de Microsoft** : Microsoft a un projet pour rendre Windows 11 plus durable en exécutant les mises à jour lorsque l'intensité carbone est plus faible.
    
* La recherche a montré que décaler les charges de travail tolérantes aux délais vers les week-ends peut **réduire les émissions de 20%**, et vers le lendemain de 5%.
    
* **Prévisions :** Nous pouvons prédire l'intensité carbone future avec une précision raisonnable grâce aux avancées de la prévision météorologique.
    

4. ### Façonnage de la Demande (Demand Shaping)
    

Le **façonnage de la demande** est une stratégie similaire au décalage, mais au lieu de déplacer la demande, nous adaptons le calcul pour qu'il corresponde à l'offre d'énergie existante.

**Principe :** **Augmenter la demande et faire plus lorsque l'intensité carbone est faible ; diminuer la demande et faire moins lorsque l'intensité carbone est élevée.**

**Exemples concrets :**

* **Mode Éco (Eco Mode) :** C'est un concept familier dans nos appareils quotidiens (voitures, machines à laver). Le mode éco sacrifie une certaine performance pour consommer moins de ressources
    
    Dans le logiciel, cela pourrait signifier une réduction automatique de la qualité du streaming vidéo lorsque la bande passante est faible.
    
* **Annulation de processus :** En tant que praticiens du logiciel vert, nous pourrions envisager d'annuler un processus lorsque l'intensité carbone est très élevée, plutôt que de le décaler, réduisant ainsi les exigences de notre application et les attentes de nos utilisateurs finaux
    

### Code “carbon-aware” en une ligne de code avec Prefect / Airflow

Si vous exécutez vos scripts Python ou entraînements IA sur **Prefect** ou **Airflow**, il suffit d’un décorateur pour rendre vos tâches sensibles à l’intensité carbone :

```yaml
@carbon_aware(max_intensity=100)
```

C’est aussi simple que ça, aucune refonte infra ou de coordination DevOps n’est nécessaire.

Le décorateur est également paramétrable selon le provider,:

```yaml
@task
@carbonaware_delay_decorator(
    provider="gcp",             # Optionnel: Provider Cloud: "aws", "azure", or "gcp"
    region="us-central1",       # Optionnel: Identifiant de la région cloud
    window=timedelta(minutes=5),# Attente maximale pour un slot optimal
    duration=timedelta(minutes=30),
)
```

Une tâche peut être utilisée à la place d’un décorateur, ce qui rend l’usage plus flexible:

```python
# Créez une task carbon-aware de report
delay = carbonaware_delay_task(
    provider="gcp",
    region="us-central1",
    window=timedelta(minutes=5),
    duration=timedelta(minutes=30),
)

# On attend le slot décarbonné optimal
delay()

# Une fois le slot identifié, on entraîne le modèle
train_model()
```

Le package carbonaware passe par le Carbon Aware SDK qui supporte les sources de données WattTime et/ou ElectricityMaps.

**Limites** :

* Le worker reste actif en attente → prévoir des ressources légères mais scalables.
    
* Si la région ou le fournisseur ne sont pas détectés, l’exécution n’est pas reportée.
    

## Modèles Architecturaux pour les Systèmes Conscients du Carbone

La mise en œuvre de l'informatique consciente du carbone nécessite une intégration intelligente des données d'intensité carbone dans nos systèmes de planification et d'orchestration.

### Intégration des Données d'Intensité Carbone

La première étape consiste à obtenir des informations fiables sur l'intensité carbone.

* **Sources de données API :** Des fournisseurs comme **WattTime** et **ElectricityMap** offrent des API avec une couverture mondiale pour les données d'intensité carbone, incluant des prévisions. WattTime fournit gratuitement une intensité carbone relative (de 1 à 100) et propose des plans payants pour accéder aux émissions marginales ou aux prévisions.
    
* **Fournisseurs de cloud hyperscale :** Des géants comme Google commencent à intégrer ces données pour leurs propres régions, souvent basées sur ElectricityMap, et mettent en évidence les régions à faible intensité carbone.
    
* **Outils open source :** Le projet **grid-intensity-go** de la Green Web Foundation comprend un exportateur de métriques Prometheus, un SDK Go et une CLI qui s'intègre à plusieurs fournisseurs de données d'intensité carbone.
    

### Comparaison des Orchestrateurs : Kubernetes vs Nomad

Les orchestrateurs sont au cœur de nos systèmes distribués et constituent des points d'intégration idéaux pour la planification consciente du carbone.

**Kubernetes** est la plateforme d'orchestration de conteneurs dominante, avec un écosystème riche et une large adoption dans l'industrie. **Nomad** d'HashiCorp offre une approche plus légère, capable d'orchestrer non seulement des conteneurs mais aussi des applications virtualisées, isolées ou natives.

Pour le scheduling conscient du carbone, les deux plateformes présentent des approches distinctes :

**Kubernetes :**

* Met l'accent sur l'extensibilité via des Custom Resource Definitions (CRDs) et des webhooks d'admission
    
* Offre le Horizontal Pod Autoscaler (HPA) qui peut être étendu avec des métriques personnalisées
    
* Permet l'implémentation de planificateurs personnalisés
    
* Le projet KEDA (Kubernetes Event-driven Autoscaling) ajoute la capacité de mise à l'échelle à zéro, utile pour économiser de l'énergie lorsque l'intensité carbone est élevée
    

**Nomad :**

* Offre nativement la fédération multi-régions, facilitant le décalage spatial
    
* Une branche expérimentale permet d'attribuer un "score carbone" à chaque nœud du cluster
    
* Son plugin d'autoscaling peut facilement intégrer des métriques d'intensité carbone
    

La principale différence est que Nomad a déjà des fonctionnalités expérimentales pour le scheduling conscient du carbone, tandis que Kubernetes nécessite plus de personnalisation mais offre une plus grande flexibilité et un écosystème plus vaste.

## Implémentation d'un Scheduler Kubernetes Conscient du Carbone

Entrons maintenant dans le vif du sujet avec une implémentation pratique basée sur le projet [carbon-aware-k8s-scheduler](https://github.com/PheonBest/carbon-aware-k8s-scheduler)

. Ce projet fournit un exemple minimal de scheduling de pods basé sur l'empreinte carbone en modifiant les affinités des pods selon l'intensité carbone marginale (MCI).

### Architecture de la Solution

Le scheduler conscient du carbone utilise un opérateur Kubernetes basé sur Kopf (Kubernetes Operator Pythonic Framework) qui :

1. Intercepte les demandes de création de pods
    
2. Évalue l'intensité carbone de chaque nœud disponible
    
3. Modifie les affinités du pod pour favoriser les nœuds à faible intensité carbone
    
4. Laisse le scheduler standard de Kubernetes placer le pod en tenant compte de ces préférences
    

### Configuration d'un Environnement de Test

Pour tester notre scheduler, nous pouvons configurer un cluster Kubernetes local avec Minikube :

```yaml
# Installation de minikube
brew install minikube

# Démarrage d'un cluster à 3 nœuds
minikube start --cpus 4 --memory 4096 --nodes 3 -p k8s

# Labelliser les nœuds avec des régions différentes
kubectl label nodes k8s region=california
kubectl label nodes k8s-m02 region=texas
kubectl label nodes k8s-m03 region=new_york

# Vérifier que les labels sont correctement appliqués
kubectl get nodes -o custom-columns=NAME:.metadata.name,REGION:.metadata.labels.region
```

Cette configuration simule un environnement multi-régions où chaque nœud représente une région avec une intensité carbone différente.

### Déploiement du Scheduler

Le déploiement du scheduler peut être effectué à l'aide du script fourni dans le dépôt :

```yaml
cd src/deployment
sudo chmod +x local_deployment.sh
./local_deployment.sh
```

Ce script crée un namespace dédié, déploie le scheduler et configure les rôles RBAC nécessaires pour que l'opérateur puisse observer et modifier les pods.

### Exploration du Code du Scheduler

Le cœur du scheduler se trouve dans le handler qui intercepte les événements de création de pods :

```yaml
@kopf.on.create('', 'v1', 'pods', when=lambda **_: ACTIVE)
def create_fn(spec, meta, namespace, logger, **kwargs):
    # Ignorer les pods système et ceux déjà schedulés
    if namespace == 'kube-system' or spec.get('nodeName') is not None:
        return
    
    logger.info(f"Traitement du pod {meta['name']}")
    
    # Récupérer l'intensité carbone de chaque nœud
    nodes_carbon_intensity = get_nodes_carbon_intensity()
    
    # Trier les nœuds par intensité carbone (du plus propre au plus sale)
    sorted_nodes = sorted(nodes_carbon_intensity.items(), key=lambda x: x[1])
    
    # Créer un patch d'affinité favorisant les nœuds propres
    pod_patch = create_node_affinity_patch(sorted_nodes)
    
    # Appliquer le patch au pod
    api = kubernetes.client.CoreV1Api()
    api.patch_namespaced_pod(
        name=meta['name'],
        namespace=namespace,
        body=pod_patch
    )
```

La fonction `create_node_affinity_patch` génère un patch qui définit des préférences d'affinité, attribuant des poids plus élevés aux nœuds avec une faible intensité carbone :

```yaml
def create_node_affinity_patch(sorted_nodes):
    preferred_during_scheduling = []
    
    # Attribuer des poids inversement proportionnels à l'intensité carbone
    max_weight = 100
    for i, (node_name, _) in enumerate(sorted_nodes):
        weight = max(max_weight - i * 10, 10)
        
        preferred_during_scheduling.append({
            'weight': weight,
            'preference': {
                'matchExpressions': [{
                    'key': 'kubernetes.io/hostname',
                    'operator': 'In',
                    'values': [node_name]
                }]
            }
        })
    
    return {
        'spec': {
            'affinity': {
                'nodeAffinity': {
                    'preferredDuringSchedulingIgnoredDuringExecution': 
                        preferred_during_scheduling
                }
            }
        }
    }
```

Cette approche utilise l'affinité préférentielle (`preferredDuringSchedulingIgnoredDuringExecution`) plutôt que requise, ce qui permet au scheduler standard de Kubernetes de continuer à fonctionner si aucun nœud optimal n'est disponible.

### Simulation de l'Intensité Carbone avec Vessim

Dans un environnement réel, nous aurions besoin de données d'intensité carbone précises. C'est là qu'intervient **Vessim**, un simulateur de microgrids qui peut fournir des données d'intensité carbone réalistes.

Voici un exemple de configuration Vessim qui simule un microgrid comprenant des serveurs, des panneaux solaires et un système de batterie :

```yaml
import vessim as vs

# Créer un environnement de simulation commençant le 15 juin 2022
# avec un pas de simulation de 5 secondes
environment = vs.Environment(sim_start="2022-06-15", step_size=5)

# Configurer un microgrid pour un cluster GPU à Berlin
microgrid = environment.add_microgrid(
    name="gpu_cluster_in_berlin",
    actors=[
        vs.Actor(name="gpu_cluster", signal=vs.PrometheusSignal(
            prometheus_url="http://localhost:30826/prometheus",
            query="sum(DCGM_FI_DEV_POWER_USAGE)",  # Consommation totale des GPUs
            username="username",
            password="password"
        ))
    ],
    # Ajouter une source d'énergie solaire basée sur des données météo réelles
    power_sources=[
        vs.SolarPV(
            name="solar_panels",
            peak_power=5000,  # 5kW capacité maximale
            weather_api=vs.SolcastAPI(
                api_key="votre_clé_api",
                latitude=52.5200, longitude=13.4050  # Berlin
            )
        )
    ],
    # Ajouter une batterie pour le stockage
    energy_storages=[
        vs.SimpleBattery(
            name="battery",
            capacity=1500,  # 1.5kWh
            initial_charge=1200,  # 80% chargée initialement
            min_charge=450,  # Ne descend jamais en dessous de 30%
        )
    ],
    # Obtenir les données d'intensité carbone marginale via WattTime
    grid_signals={
        "mci_index": vs.WatttimeSignal(
            username="username",
            password="password",
            location=(52.5200, 13.4050),  # Berlin
        )
    },
)

# Exposer le microgrid via une API REST
rest_api = vs.Api([microgrid], export_prometheus=True)
environment.add_controller(rest_api)

# Exécuter la simulation pendant 24 heures en temps réel
environment.run(until=24 * 3600, rt_factor=1)
```

Cette simulation peut être exécutée en parallèle avec notre cluster Kubernetes, fournissant des données d'intensité carbone réalistes que notre scheduler peut consommer.

### Extension avec le Horizontal Pod Autoscaler

On peut également reporter les tâches non urgentes pour profiter des heures creuses / d’énergies propres. C’est le déplacement temporel de la charge, qu’on réalise avec le Horizontal Pod Autoscaler (HPA) de Kubernetes.

Le HPA peut être configuré pour utiliser l'intensité carbone comme une métrique personnalisée. Quand l'intensité carbone dépasse un certain niveau, le HPA peut diminuer le nombre de réplicas, reportant ainsi le travail à un moment où l'intensité carbone est plus basse:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: carbon-aware-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: batch-processing
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: External
    external:
      metric:
        name: grid_intensity_carbon_relative
      target:
        type: Value
        value: 50
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
```

Cette configuration réduit le nombre de répliques lorsque l'intensité carbone relative dépasse 50%, avec une fenêtre de stabilisation de 5 minutes pour éviter les fluctuations rapides.

Le projet [KEDA](https://keda.sh/) (Kubernetes Event-driven Autoscaling) va encore plus loin en permettant la mise à l'échelle à zéro, idéale pour les charges de travail par lots qui peuvent être entièrement reportées.

## Considérations Pratiques et Compromis

L'implémentation d'un scheduler conscient du carbone implique plusieurs compromis qui doivent être soigneusement évalués :

### Identification des Charges de Travail Adaptées

Toutes les charges de travail ne sont pas adaptées au décalage temporel ou spatial :

* **Idéales pour le décalage :** formation de modèles ML, analyse de données, sauvegardes, rendu vidéo, mises à jour logicielles
    
* **Moins adaptées :** services interactifs avec des exigences de latence strictes, applications critiques en temps réel
    

### Latence vs Empreinte Carbone

Le décalage spatial peut augmenter la latence pour les utilisateurs finaux. Il est essentiel de définir des seuils acceptables et de mesurer l'impact sur l'expérience utilisateur.

### Souveraineté des Données

Les réglementations de souveraineté des données peuvent restreindre les possibilités de décalage spatial. Assurez-vous que votre stratégie respecte les contraintes légales applicables.

### Carbone Intégré vs Carbone Opérationnel

Si le sur-provisionnement de serveurs est nécessaire pour permettre le décalage spatial, l'augmentation du carbone intégré (émis lors de la fabrication) pourrait annuler les gains du carbone opérationnel (émis lors de l'utilisation).

## Conclusion et Perspectives d'Avenir

Le carbon-aware est clairement une opportunité pour respectez nos engagements environnementaux, en maintenant les performances et en limitant le coût des infrastructures.

De manière pratique, on a pu mettre en place un scheduling minimal. Cette prise de décision peut se faire avec des techniques plus avancées, comme la **théorie des jeux multi-agents**: Chaque puce évaluerait ses besoins en énergie, anticipe la demande en énergie des autres, et module sa consommation par rapport à l’ensemble du système. C’est une prise de décision **décentralisée**.

Pour une solution de production complète, plusieurs améliorations seraient nécessaires :

* Mise à jour continue des affinités pendant la durée de vie des pods
    
* Intégration avec des API d'intensité carbone en temps réel
    
* Prise en compte d'autres facteurs comme la charge des nœuds et les contraintes de ressources. En effet, l**e meilleur rendement énergétique des serveurs d’un datacenter n’est pas à charge maximale**, on peut donc essayer de se rapprocher au maximum de la charge avec le meilleur rendement.
    
* Utilisation de prévisions d'intensité carbone pour une planification proactive
    

Les recherches récentes dans ce domaine sont prometteuses, avec des réductions d'empreinte carbone de plus de 30% sans impact significatif sur les performances. À mesure que les réglementations environnementales se renforcent et que la pression pour des infrastructures numériques durables augmente, l'adoption de pratiques conscientes du carbone deviendra non seulement un avantage écologique mais aussi économique et stratégique.

## Ressources Complémentaires

• **The Green Web Foundation** : [https://www.greenwebfoundation.org/](https://www.google.com/url?sa=E&q=https%3A%2F%2Fwww.greenwebfoundation.org%2F)

• **Green Software Foundation** : [https://greensoftware.foundation/](https://www.google.com/url?sa=E&q=https%3A%2F%2Fgreensoftware.foundation%2F)

• **WattTime** : [https://www.watttime.org/](https://www.google.com/url?sa=E&q=https%3A%2F%2Fwww.watttime.org%2F)

• **ElectricityMap** : [https://www.electricitymaps.com/](https://www.google.com/url?sa=E&q=https%3A%2F%2Fwww.electricitymaps.com%2F)

• **Vessim GitHub Repository** : [https://github.com/dos-group/vessim](https://www.google.com/url?sa=E&q=https%3A%2F%2Fgithub.com%2Fdos-group%2Fvessim)

• **LinTS Paper (arXiv)** : [https://arxiv.org/abs/2410.01597](https://www.google.com/url?sa=E&q=https%3A%2F%2Farxiv.org%2Fabs%2F2410.01597)

• **Cloud Carbon Footprint** : [https://www.cloudcarbonfootprint.org/](https://www.google.com/url?sa=E&q=https%3A%2F%2Fwww.cloudcarbonfootprint.org%2F)

• **Green IT Deployment: Reduce Enterprise Scheduling Carbon Footprint** : [https://myshyft.com/blog/green-it-deployment-reduce-enterprise-scheduling-carbon-footprint](https://www.google.com/url?sa=E&q=https%3A%2F%2Fmyshyft.com%2Fblog%2Fgreen-it-deployment-reduce-enterprise-scheduling-carbon-footprint)