# Sistema de Monitoramento Veicular AIoT (Driver Behavior Profiling)

![Status](https://img.shields.io/badge/Status-Concluído-success)
![Language](https://img.shields.io/badge/Firmware-C_%7C_STM32-blue)
![Backend](https://img.shields.io/badge/Backend-Python_%7C_AWS-orange)
![ML](https://img.shields.io/badge/AI-XGBoost_%7C_Optuna-red)

## 📖 Sobre o Projeto
Uma solução completa de AIoT (*Artificial Intelligence of Things*) para perfilamento de comportamento de motoristas em tempo real. O sistema integra hardware embarcado customizado, conectividade LTE via MQTT seguro e um backend Serverless na AWS que executa modelos de Machine Learning para classificar a condução como **Segura**, **Normal** ou **Agressiva**.

Este projeto foi desenvolvido como Trabalho de Conclusão de Curso (TCC) em Engenharia Elétrica na Universidade Federal do Paraná (UFPR).

---

## 📑 Índice
1. [Visão Geral da Arquitetura](#-visão-geral-da-arquitetura)
2. [Hardware (PCB e Componentes)](#-hardware-pcb-e-componentes)
3. [Firmware (STM32)](#-firmware-stm32)
4. [Machine Learning e Dados](#-machine-learning-e-dados)
5. [Infraestrutura Cloud (AWS)](#-infraestrutura-cloud-aws)
6. [Resultados e Performance](#-resultados-e-performance)
7. [Estrutura do Repositório](#-estrutura-do-repositório)
8. [Como Executar](#-como-executar)

---

## 🏗 Visão Geral da Arquitetura

O sistema opera em ciclo fechado: o hardware coleta dados inerciais, processa filtros na borda e transmite via 4G para a nuvem. A AWS processa os dados, executa a inferência da IA e retorna o feedback para o dispositivo e para o dashboard em tempo real.

```mermaid
graph LR
    A[Veículo/Sensores] -->|I2C 400kHz| B(STM32F103)
    B -->|UART/AT| C(Modem LTE A7670SA)
    C -->|MQTT/TLS 1.2| D[AWS IoT Core]
    D -->|Gatilho JSON| E[AWS Lambda Docker]
    E -->|Inferência| F((Modelo XGBoost))
    E -->|Persistência| G[DynamoDB/S3]
    E -->|Feedback| H[Dashboard Streamlit]
    E -.->|Pub Ack| C


🔌 Hardware (PCB e Componentes)O hardware foi projetado para operar em ambiente veicular ruidoso, com filtragem mecânica e digital.MCU: STM32F103C8T6 (ARM Cortex-M3 @ 72MHz).Conectividade: Módulo SIMCom A7670SA (LTE Cat 1 / 4G), com suporte nativo a SSL/TLS.Sensores: MPU-6050 (Acelerômetro e Giroscópio 6-DOF) via barramento I2C.Alimentação: Conversor Buck DC-DC (12V -> 5V) para suportar picos de corrente do modem e LDOs de 3.3V.Nota: Os arquivos de fabricação (Gerbers) e esquemáticos da versão mais recente da placa estão disponíveis na pasta /hardware_pcb.

💻 Firmware (STM32)Desenvolvido em C utilizando a STM32 HAL API. O firmware implementa uma Máquina de Estados Finitos (FSM) para gerenciar a coleta assíncrona e a transmissão.Destaques Técnicos:Filtro DLPF: Configuração de hardware do MPU-6050 com corte em 10Hz (Reg 0x05) para eliminar ruído de vibração do motor.Ring Buffers: Implementação de buffers circulares para captura de contexto "pré-evento" e "pós-evento" (100 amostras totais por janela).Segurança: Implementação de TLS 1.2 com autenticação mútua (Certificados X.509) injetados no modem.Gestão de Memória: Otimização para rodar em 20KB de RAM, ocupando apenas ~14% com buffers.

🧠 Machine Learning e DadosO núcleo de inteligência utiliza um modelo XGBoost otimizado via Optuna.Dataset: Dados reais coletados em 234km de rodagem urbana (Curitiba) + Dados sintéticos gerados no simulador Assetto Corsa.Engenharia de Atributos: 168 features extraídas por janela, incluindo métricas no Domínio do Tempo, Frequência (FFT), Jerk e Energia.Classes: Safe (Seguro), Normal, Aggressive (Agressivo).Balanceamento: Uso de SMOTE para correção de classes minoritárias durante o treino.

☁️ Infraestrutura Cloud (AWS)Arquitetura Serverless para escalabilidade e baixo custo.AWS IoT Core: Broker MQTT seguro com regras de roteamento.AWS Lambda: Executa um contêiner Docker com as bibliotecas scikit-learn e xgboost para inferência.Zero Motion Gate: Lógica na nuvem que descarta processamento pesado se o veículo estiver parado, economizando custos.Dashboard: Aplicação Streamlit hospedada em EC2 para visualização de telemetria e KPIs em tempo real.

📊 Resultados e PerformanceO sistema foi validado em campo e apresentou os seguintes resultados:MétricaValorDescriçãoF1-Score Global0.95Alta precisão na classificação de risco (Teste Holdout).Latência Média5.25sTempo total (Evento -> Nuvem -> Dashboard) via 4G.Latência Lambda26msTempo de inferência do modelo após warm start.Confiabilidade100%Sessão MQTT mantida mesmo em zonas de sombra (-113 dBm).

📂 Estrutura do RepositórioEste repositório adota uma estrutura de Monorepo para centralizar todo o desenvolvimento:PlaintextMeu-Projeto-IoT/
│
├── /firmware_stm32       # Código Fonte C (STM32CubeIDE)
│   ├── /Core             # Main, Drivers (A7670, MPU6050)
│   └── certificates.c    # Template para certificados AWS (Segurança)
│
├── /hardware_pcb         # Arquivos de Design Eletrônico
│   ├── /gerbers          # Arquivos de fabricação
│   └── /schematics       # Diagramas PDF/KiCad
│
├── /backend_lambda       # Função Serverless (Docker)
│   ├── /src              # Script de inferência Python e carregamento de modelos
│   └── Dockerfile        # Configuração do container
│
├── /machine_learning     # Pipeline de Treinamento
│   ├── /notebooks        # Jupyter Notebooks (EDA, Treino, Optuna)
│   ├── /models           # Modelos treinados (.joblib) e Scalers
│   └── /src              # Scripts de Feature Engineering e Pré-processamento
│
├── /simulation_ac        # Integração Assetto Corsa
│   └── telemetry_ac.py   # Script de extração de dados do simulador via Shared Memory
│
└── /dashboard            # Aplicação Web (Streamlit)
    └── app.py            # Interface de visualização em tempo real

🚀 Como Executar
1. FirmwareAbra o projeto na pasta /firmware_stm32 com o STM32CubeIDE.Renomeie certificates.c e insira suas chaves do AWS IoT Core.Compile e grave no STM32F103 via ST-Link.

2. Machine LearningInstale as dependências: pip install -r machine_learning/requirements.txt.Execute o notebook de treinamento ou carregue o modelo pré-treinado em /models.

3. Backend & DashboardFaça o deploy da imagem Docker na AWS Lambda (ECR).Configure as regras de roteamento no AWS IoT Core para o tópico veiculos/+/eventos.

Rode o dashboard localmente ou no EC2:Bashcd dashboard

streamlit run app.py

📜 LicençaEste projeto é distribuído sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.Autor: Gustavo Puerari AraujoEngenheiro Eletricista | Ênfase em Eletrônica e Telecomunicações

