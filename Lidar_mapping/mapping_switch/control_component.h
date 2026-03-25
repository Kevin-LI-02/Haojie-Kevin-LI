/*
 * control_component.h
 *
 *  Created on: 2024年3月12日
 *      Author: wangege
 */

#ifndef SRC_CONTROL_COMPONENT_H_
#define SRC_CONTROL_COMPONENT_H_

#include "control_interface_def.h"
#include "dlt.h"
#include "./input/input.h"
#include "./output/output.h"
#include <memory>
#include "vehicle_state_provider.h"
#include "libconfig.h"
#include "./controller/lat_controller/lat_controller.h"
#include "./controller/lon_controller/lon_controller.h"
//#include "./controller/precise_parking_controller/precise_parking_controller.h"
#include <stdlib.h>
#include <unistd.h>
#include "uclib/osal/osal_time.h"
#include "safety_guardian.h"
#include "./nanomsg/nanomsg_comm.h"
#include "planner/LocalPlanner.h"
#include "simulation/Vehicle.h"
#include "utils/JsonParser.h"  // 用于加载地图
#include "utils/MathTypes.h"   // 用于 tp::Point, tp::Vector
#define CONTROL_CONFIG_FILE  "/etc/echiev/control_new/control_conf.cfg"



/**
 * @brief 控制组件，此为主功能类，负责调用其他类，以实现控制模块的各种功能
 *
 * 该类会调用以下功能类：
 *     轨迹分析器（TrajectoryAnalyzer）、车辆状态提供器（VehicleStateProvider）、
 *     纵向控制器（LonController）、横向控制器（LatController）、
 *     精准停车控制器（PreciseParkingController）、安全保护器（SafetyGuardian）、
 *     数据输入（Input）、数据输出（Output）、nanomsg通信（NanomsgCommunication）
 * 以实现控制模块所需的功能。
 */
class ControlComponent {
public:
	ControlComponent();
	~ControlComponent() = default;
	bool Init();
	bool Proc();
private:
	bool NetworkFrameInput();
	void ProduceControlCommand(const LocalView* local_view,
			const std::shared_ptr<VehicleStateProvider> vehicle_state,
			ControlCommand* control_command);
	void OtherControlCommandCompute(const LocalView* local_view,
			const std::shared_ptr<VehicleStateProvider> vehicle_state,
			ControlCommand* control_command);
	void UpdateGearCommand(ControlCommand* control_command,
			const std::shared_ptr<VehicleStateProvider> vehicle_state);
	void UpdateLightCommand(ControlCommand* control_command);
	void DltLogOutput();
	void DltLogOutputConfig();

	bool ReadControlConfig(std::shared_ptr<ControlConfig> control_config);
	bool ReadLongitudinalControlConfig(config_t* strCfg,
			std::shared_ptr<ControlConfig> control_config);
	bool ReadPureSpeedControllerConfig(config_t* strCfg,
			std::shared_ptr<ControlConfig> control_config);
	bool ReadBasedPreviewPidControllerConfig(config_t* strCfg,
			std::shared_ptr<ControlConfig> control_config);
	bool ReadLateralControlConfig(config_t* strCfg,
			std::shared_ptr<ControlConfig> control_config);
	bool ReadSafetyGuardianConfig(config_t* strCfg,
			std::shared_ptr<ControlConfig> control_config);

	// [New] 辅助函数声明
    void RunInternalPlanner();
    //加载 CSV 轨迹文件
    bool LoadTrajectoryFromCSV(const std::string& file_path);
    //运行 CSV 回放规划器
    void RunCSVPlaybackPlanner();
private:
	/**
	 * @brief 包含控制配置文件的接口所有定义
	 *
	 * 读取control_conf.cfg配置文件后，所有的数值存储在该实体变量中。
	 */
	std::shared_ptr<ControlConfig> control_config_ = std::make_shared<
			ControlConfig>();

	// [New] 增加规划器实例指针
	std::shared_ptr<tp::LocalPlanner> local_planner_;
	// 存储从 CSV 读取的完整全局路径
	std::vector<STR_PLANNING> csv_global_path_;

	/**
	 * @brief DLT日志系统全局变量
	 *
	 * 所有需要使用DLT日志打印的类都需要传入该实体变量。
	 */
	std::shared_ptr<DltContext> dlt_ctx_ = std::make_shared<DltContext>();
	/**
	 * @brief 轨迹分析器实体变量定义
	 *
	 * 轨迹分析器主要用于确定匹配点和预瞄点的位置坐标、曲率、航向角等，以用于横向和纵向控制。
	 */
	std::shared_ptr<TrajectoryAnalyzer> trajectory_analyzer_ = std::make_shared<
			TrajectoryAnalyzer>(dlt_ctx_, control_config_);

	/**
	 * @brief 接收定位、规划、底盘信息的实体变量定义
	 *
	 * 从Input中通过网络报文读取定位（9110）、规划（9112）、底盘（9125）数据，
	 * 只有报文更新的时候才更新，以节省算力。
	 */
	STR_FUSIONLOC latest_localization_;
	STR_PLANNING_DATA latest_trajectory_;
	ctrl_status_t latest_chassis_;
	STR_LIDAR_DATA latest_lidar_;
	STRU_LANE_DITCH latest_lane_ditch_;
	STRU_LOC_MARK latest_loc_mark_;
	std::vector<STR_ALARM_CODE> latest_alarm_vec_;
	/**
	 * @brief 匹配点、预瞄点和最大曲率的实体变量定义
	 *
	 * 用于存储从轨迹分析器读进来的匹配点、预瞄点和轨迹的最大曲率。
	 */
	MatchPoint mp_point_[2];
	double max_kappa_;
	/**
	 * @brief 局部视图用于存储全局输入信息
	 *
	 * 全局输入信息包括定位、规划、底盘、匹配点、预瞄点、最大曲率等信息，
	 * 这些信息后续会传递给其他模块，以方便读取。
	 */
	LocalView local_view_;
	/**
	 * @brief 控制命令的实体定义
	 *
	 * 包含着底盘的转向、速度、油门刹车、转向灯等命令信息，这些信息最终会发送给底盘执行。
	 */
	ControlCommand control_command_;
	/**
	 * @brief 调试器实体定义
	 *
	 * 在程序运行过程中所产生的中间变量和最终输出结果都会在此记录，方便使用和调试。
	 */
	Debug debug_;
	int nanomsg_io_control_ = 0;
	char nanomsg_plan_gear_ = 0;
	/**
	 * @brief 安全保护、精准停车开关
	 *
	 * 详细定义见配置文件。
	 */
	bool enable_safety_guardian_ = true;
	bool enable_precise_parking_control_ = false;
	bool enable_6666_port_receive_lidar_ = false;
	bool enable_AEB_protect_ = false;
	bool enable_lane_ditch_protect_ = false;
	const char* longitudinal_control_mode_ = "throttle_brake";
	double steering_transmission_ratio_;
	/**
	 * @brief 输入类和输出类的实体定义
	 *
	 * 输入类功能是用于接收规划、定位、底盘信息；
	 * 输出类功能是用于控制命令和报警信息的发送。
	 */
	std::shared_ptr<Input> input_ = std::make_shared<Input>(dlt_ctx_);
	std::shared_ptr<Output> output_ = std::make_shared<Output>(dlt_ctx_);
	/**
	 * @brief 车辆状态提供器
	 *
	 * 用于解析车辆实时状态，主要包括实时定位（位置、航向角、pitch角、航向角变化率等）
	 * 和底盘状态信息（速度、档位、油门、刹车、驻车等）。
	 */
	std::shared_ptr<VehicleStateProvider> vehicle_state_ = std::make_shared<
			VehicleStateProvider>(dlt_ctx_, control_config_);
	/**
	 * @brief 纵向控制器
	 *
	 * 提供了2种控制方法，包括纯速度控制和基于油门刹车的控制。
	 */
	std::shared_ptr<LonController> longitudinal_controller_ = std::make_shared<
			LonController>(dlt_ctx_, control_config_);
	/**
	 * @brief 横向控制器
	 *
	 * 提供非预瞄LQR控制方式。
	 */
	std::shared_ptr<LatController> lateral_controller_ = std::make_shared<
			LatController>(dlt_ctx_, control_config_);
	/**
	 * @brief nanomsg通信
	 *
	 * 提供nanomsg接收和发送通信方式，以和规划、remote模块进行通信。
	 */
	std::shared_ptr<NanomsgCommunication> nanomsg_communication_ =
			std::make_shared<NanomsgCommunication>(dlt_ctx_, control_config_);
	/**
	 * @brief 精准停车控制器
	 *
	 * 提供精准停车的控制方法。
	 */
//	std::shared_ptr<PreciseParkingController> precise_parking_controller_ =
//			nullptr;
	/**
	 * @brief 安全保护模块定义
	 *
	 * 对于自动驾驶中产生的故障，进行安全保护，防止车辆失控。
	 */
	std::shared_ptr<SafetyGuardian> safety_guardian_ = nullptr;

	bool is_vehicle_remote_mode_ = false;
};
#endif /* SRC_CONTROL_COMPONENT_H_ */
