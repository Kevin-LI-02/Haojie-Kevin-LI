# 嗨，我是李浩杰！👋

### 🐟 一个试图让机器人学会“看世界”的计算机视觉研究生

<div align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&pause=1000&color=2E97F7&center=true&vCenter=true&width=435&lines=Visual+Perception+Researcher;Robotics+Enthusiast;LLM+Practioner;Making+Machines+See+the+World" alt="Typing SVG" />
</div>

---

## 📖 关于我

- 🎓 **北京交通大学** | 控制科学与工程 学术硕士（推免） | GPA 90.55/100 (2/13)
- 🔭 **研究方向**：计算机视觉感知 | 特种机器人 | 大语言模型工程落地
- 🌟 **高光时刻**：日内瓦国际发明展银奖 | 挑战杯全国特等奖 | ITSC/IROS顶会论文作者
- 💼 **实习经历**：九号公司-未岚大陆（视觉算法实习生）| 香港铁路有限公司（Engineering Intern）
- 📫 **联系我**：24120172@bjtu.edu.cn | 188-1075-7598
- ⚡ **一句话自评**：项目实践经历丰富，擅长技术研发与写作，自驱力MAX，沟通力在线！

---

## 🛠️ 技术能力

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![C++](https://img.shields.io/badge/C++-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)
![MATLAB](https://img.shields.io/badge/MATLAB-0076A8?style=for-the-badge&logo=mathworks&logoColor=white)

![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![PaddleOCR](https://img.shields.io/badge/PaddleOCR-013243?style=for-the-badge&logo=paddlepaddle&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-00FFFF?style=for-the-badge&logo=yolo&logoColor=black)

![ROS](https://img.shields.io/badge/ROS-22314E?style=for-the-badge&logo=ros&logoColor=white)
![SLAM](https://img.shields.io/badge/SLAM-FF6F00?style=for-the-badge&logo=robotframework&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![LaTeX](https://img.shields.io/badge/LaTeX-008080?style=for-the-badge&logo=latex&logoColor=white)

</div>

## 💼 实习与项目精选

---

### 🚇 **香港铁路有限公司（MTR）- Engineering Intern** `2024.06—2025.07（研究至今）`
*第一负责人主导的两个核心系统，获日内瓦国际发明展银奖*

#### 📌 **ATS视觉监控系统 EYES-T**
- **技术栈**：`PaddleOCR` `OpenCV` `实时监控`
- **项目描述**：

港铁在运营控制中心有一套叫做ATS的系统，专门用来显示列车运行状态和各种报警信息。但这套系统本身没有对外开放的数据接口，我们没有办法直接从它的数据库里拿数据。所以我的思路是绕过接口限制，直接对屏幕画面做计算机视觉处理——用摄像头或者虚拟摄像头捕获ATS界面的实时画面，然后通过PaddleOCR做文字识别、结合OpenCV做图像处理，把屏幕上显示的报警信息解析出来，转化成结构化数据。识别到报警后，系统会立即触发多渠道的推送通知，包括声音报警、企业微信Webhook、邮件通知，整个延迟控制在0.3到0.4秒以内。

- **核心贡献**：
  - 构建基于PaddleOCR+OpenCV的界面信息解析pipeline
  - 实现屏幕关键状态信息实时提取、结构化解析与报警推送

📂 **项目代码**：👉 [`/EYES_T`](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/tree/main/EYES_T)
包含OCR识别模块、报警推送系统完整实现、部署教程

- **项目展示**：

##### 🏗️ EYES-T系统架构图
![EYES-T系统架构图](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/eyes_architecture.png)

##### 🎥 日内瓦展示视频【视频，点击即可跳转查看】
[![日内瓦展示视频](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/geneva_cover.png)](https://youtu.be/v1CZFK0PGQE)

##### 📸 日内瓦发明展现场
![日内瓦发明展现场](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/geneva_photos.png)

#### 📌 **智能运维助手 AI Assistant**
- **技术栈**：`RAG` `LLM` `LangChain` `知识库构建`
- **项目描述**：
  
运维人员在日常工作中面临两个痛点：一是积累了大量历史报警日志，但查询起来非常繁琐；二是故障处置操作手册是纸质或静态文档，遇到紧急情况很难快速找到对应的处置步骤。我的解决方案是把这两类数据——DAL Logs历史报警记录和Work Instructions操作手册都导入一个基于ChromaDB的向量数据库，构建知识库，然后部署本地的Qwen2.5-7B大语言模型，设计了一套RAG检索增强生成的流程。用户用自然语言提问，系统自动判断问题类型，智能决定是去查历史日志还是查操作手册，再把检索结果送给大模型生成回答。整个系统通过Flask提供Web服务，前端是一个响应式的HTML界面，还实时监控获取EYES-T检测到的报警信息，**做到报警数据与问答功能的联动**。

- **核心贡献**：
  - 设计RAG架构实现故障操作流程的实时检索与智能问答
  - 显著提升运维人员故障排查效率

📂 **项目代码**：👉 [`/AI_Assistant`](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/tree/main/AI_Assistant)  
包含：RAG检索系统、ChromaDB知识库构建、Qwen2.5-7B本地部署、Flask Web服务、部署教程

- **项目展示**：

##### 🏗️ AI Assistant系统架构图
![AI Assistant系统架构图](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/ai_assistant_architecture.png)

##### 🔄 RAG架构图
![RAG架构图](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/rag_architecture.png)

##### 🎥 AI Assistant演示【视频，点击即可跳转查看】
[![AI Assistant演示](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/ai_assistant_cover.png)](https://youtu.be/mdYtj0TcpKo)

#### 🏆 **项目成果**
- 🥈 日内瓦国际发明展 **银奖**（学生第一发明人）
- 📄 交通领域国际顶会 **ITSC论文1篇**（第一作者）
- 📜 国家发明专利1项（第二发明人）
- 💾 软件著作权1项（第一著作权人）

---

### 🚜 **Cooper割草机场景感知分割算法** `2025.09—2026.01`
*九号-未岚大陆科技股份有限公司 · 视觉算法实习生*

- **技术栈**：`MobileNet` `HRNet` `语义分割` `数据增强` `ROS`
- **项目描述**：构建割草机场景语义分割pipeline，让机器人分清草坪和障碍物
- **核心贡献**：
  - 针对草坪与障碍物场景设计数据增强与模型训练策略
  - **使mIoU提升约3%**，显著提升复杂光照与边缘场景下freespace感知鲁棒性
  - 参与构建数据闭环系统，使模型迭代效率提升近一倍
  - 开发自动化脚本用于benchmark对比与问题数据可视化分析
- **项目展示**：由于涉及到公司保密数据，不便进行展示。

---

### 🐟 **仿蝠鲼潜水器视觉自主感知系统** `2023.10—2024.12`
*自然科学横向项目 · 项目第一负责人*

- **技术栈**：`双目视觉` `YOLOv8` `ArucoMarker` `ROS` `SLAM`
- **项目亮点**：让仿生机器鱼在水下也能“擦亮眼”，自主完成环境感知与目标识别
- **核心贡献**：
  - 设计基于双目视觉的水下感知系统，利用ArucoMarker实现高精度建图与视觉定位（marker_mapper）
  - 基于YOLOv8构建水下目标检测算法，实现实时检测与识别
  - 完成算法在仿生蝠鲼航行器平台的部署与集成

📂 **项目代码**：👉 [`/marker_mapper`](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/tree/main/marker_mapper) 
包含：双目视觉定位模块、ArucoMarker建图、ROS部署代码、部署教程

- **项目展示**：

##### 🖼️ 双目避障效果图
![双目避障效果图](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/bizhang.jpg)

##### 🎥 三维地图构建【视频，点击即可跳转查看】
[![三维地图构建](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/marker_mapper.png)](https://youtu.be/OCBbE1mW5t8)

##### 🎥 水下定位第一视角【视频，点击即可跳转查看】
[![水下定位第一视角](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/dingwei.png)](https://youtu.be/2mvpK0r1WKU)

##### 🎥 水下目标检测与跟踪【视频，点击即可跳转查看】
[![水下目标检测与跟踪](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/underwater_detection.png)](https://youtu.be/-q-ojGpyATA)

##### 🎥 航行器自主游动【视频，点击即可跳转查看】
[![航行器自主游动](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/robot_fish.png)](https://youtu.be/oO9jJrEBqqY)

- **论文成果**：机器人领域国际顶会 **IROS论文1篇**

---

### 🌉 **济南黄河大桥公路巡检机器人** `2023.06—2024.06`
*山东高速集团横向项目*

- **技术栈**：`STM32` `Jetson Nano` `YOLOv5` `嵌入式部署`
- **项目描述**：无接触式全天候自动化巡检设备，保障路面安全
- **核心贡献**：基于STM32与Jetson Nano部署YOLOv5算法实现路面病害实时检测

---

### 🏭 **脱硫塔自主飞行巡测无人机** `2022.04—2023.09`
*国家能源集团龙源环保公司横向项目*

- **技术栈**：`SLAM` `激光雷达` `路径规划` `无人机`
- **项目描述**：无GPS信号下的塔内定位建图、路径规划与壁面破损检测
- **核心贡献**：融合飞行高度计和激光雷达点云的SLAM建图算法研发
- **项目展示**：

##### 🎥 SLAM建图动态演示【视频，点击即可跳转查看】
[![SLAM建图动态演示](https://github.com/Kevin-LI-02/Haojie-Kevin-LI/raw/main/assets/images/slam.png)](https://youtu.be/RI4ZS93DJ8A)

---

## 📄 科研成果

### 学术论文

| 论文标题 | 发表情况 | 角色 |
|:---------|:---------|:-----|
| HAIRS: A Perception-Retrieval Fusion Framework for Real-time Railway Intelligent Decision Support | 投稿至2026 IEEE ITSC<br>*(交通领域国际顶会)* | **第一作者** |
| Application of soft constraints on mirror position to improve robustness of optical target positioning in shallow water | 2025 IEEE/RSJ IROS<br>*(机器人领域国际顶会)* | 学生第二作者 |

### 专利与软著

| 类型 | 名称 | 状态/编号 | 角色 |
|:-----|:-----|:----------|:-----|
| 发明专利 | 一种基于图像识别与人工智能的轨道交通监控及决策方法及装置 | 已受理 | 第二发明人 |
| 软件著作权 | 轨道交通人工智能实时监控识别与告警系统 V1.0 | 软著登字第16979828号 | **第一著作权人** |

---

## 🏆 科研竞赛高光时刻

> **累计获得国家级及以上奖项4项，省部级奖项14项，校级奖项10余项**

| 年份 | 竞赛名称 | 获奖等级 | 项目名称 | 角色 |
|:----:|:---------|:--------:|:---------|:-----|
| 2025 | 日内瓦国际发明展 | **国际银奖** | AI Powered Monitoring System | **学生第一负责人** |
| 2025 | 第十九届“挑战杯”全国大学生课外学术科技作品竞赛 | **全国特等奖** | TOTA瞬界-爆燃推进式水空穿梭跨介质航行器 | 核心成员 |
| 2025 | 第十九届“挑战杯”全国大学生课外学术科技作品竞赛 | **全国二等奖** | 低空飞行器集群发射与回收创新设计 | 核心成员 |
| 2025 | 中国国际大学生创新大赛北京赛区 | 北京市一等奖 | 智云科技-面向复杂电力系统环境的多形态机器人集群产业协同方案领航者 | 核心成员 |
| 2025 | 中国国际大学生创新大赛北京赛区 | 北京市二等奖 | TOTA瞬界-爆燃推进式多模态水空穿梭跨介质航行器 | 核心成员 |
| 2025 | 第二十届中国研究生电子设计竞赛 | 北京市二等奖 | 国内领先基于水电站复杂管道场景的全面感知智能无人巡检机器人 | **学生负责人** |
| 2025 | “青创北京”挑战杯首都大学生课外学术科技作品竞赛 | **北京市特等奖** | 基于柔性八轮结构与多传感器融合AI增强技术的管道巡检领航者 | **学生负责人** |
| 2025 | “青创北京”挑战杯首都大学生课外学术科技作品竞赛 | 北京市二等奖 | TOTA瞬界-爆燃推进式多模态水空穿梭跨介质航行器 | 核心成员 |
| 2025 | “青创北京”挑战杯首都大学生课外学术科技作品竞赛 | 北京市二等奖 | 广域多场景覆盖的轨道交通智能感知虚拟平台 | 核心成员 |
| 2024 | 中国国际大学生创新大赛 | **国家级银奖** | 国内首创基于柔性八轮结构与多姿态激光雷达的密闭管道巡检领航者 | **学生负责人** |
| 2024 | 中国国际大学生创新大赛北京赛区 | 北京市一等奖 | 国内首创基于柔性八轮结构与多姿态激光雷达的密闭管道巡检领航者 | **学生负责人** |
| 2024 | 中国国际大学生创新大赛北京赛区 | 北京市二等奖 | 智云科技-国内领先基于水电站复杂管道场景的全面感知智能无人巡检机器人 | **学生负责人** |
| 2024 | 中国国际大学生创新大赛北京赛区 | 北京市二等奖 | 智巡科技-大基建背景下的开放空间轨道式智能无人巡检系统 | 核心成员 |
| 2024 | 第十九届中国研究生电子设计竞赛 | 北京市二等奖 | 轨道交通巡检机器人 | 核心成员 |
| 2024 | 第三届“京彩大创”北京大学生创新创业大赛 | 北京市二等奖 | 国内首创基于柔性八轮结构与多姿态激光雷达的密闭管道巡检领航者 | **学生负责人** |
| 2023 | 全国大学生电子设计竞赛 | 北京市三等奖 | 运动目标控制与自动追踪系统 | **学生负责人** |
| 2023 | 全国大学生统计建模大赛 | 北京市三等奖 | 中国式现代化视角下的共同富裕与高等教育、乡村振兴耦合协调的时空演变及影响因素挖掘-基于Tobit回归模型 | **学生负责人** |
| 2023 | 北京市优秀创新创业项目 | 北京市级 | 可连续喷水的高集成度推进器设计、搭建与实验优化 | 核心成员 |

---

## 🎖️ 荣誉奖项

- **2025**：交控科技专项奖学金 (排名1) | 研究生一等学业奖学金 | 研究生社会工作优秀奖学金 | 优秀研究生干部 | 优秀共青团员
- **2024**：研究生一等学业奖学金 | 北京市优秀毕业生 | 北京交通大学优秀毕业生
- **2023**：一等学习优秀奖学金 | 三好学生 | 优秀共青团员
- **2022**：二等学习优秀奖学金 | 三好学生 | 优秀共青团员 | 寒暑期社会实践活动优秀团长、优秀实践个人
- **2020**：朋辈帮扶优秀辅导师

