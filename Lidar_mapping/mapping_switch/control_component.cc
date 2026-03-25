/*
 * control_component.cc
 *
 *  Created on: 2024年3月12日
 *      Author: wangege
 */

#include "control_component.h"
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <limits>
#include <algorithm>
int main(void) {
	std::shared_ptr<ControlComponent> control_object = std::make_shared<
			ControlComponent>();

	if (!control_object->Init()) {
		printf("@control_object->Init function execute fail!!!@  \n");
		exit(1);
	}

	while (1) {
		const auto start_time = time_now_us();

		control_object->Proc();

		const auto end_time = time_now_us();
		auto program_running_time = llabs(end_time - start_time);
		if (program_running_time > 9920) {
			program_running_time = 9920;
		}
		usleep(9930 - program_running_time);
	}
	return 0;
}

/**
 * @brief ControlComponent-类构造函数
 *
 * 对local_view_变量进行初始化，local_view_中定义了指针变量，
 * 初始化正是要给这些指针变量赋值。
 *
 * @note 无。
 */
ControlComponent::ControlComponent() {
	local_view_.localization = &latest_localization_;
	local_view_.trajectory = &latest_trajectory_;
	local_view_.chassis = &latest_chassis_;
	local_view_.matched_preview_point = mp_point_;
	local_view_.max_kappa = &max_kappa_;
	local_view_.lane_ditch = &latest_lane_ditch_;
	local_view_.loc_mark = &latest_loc_mark_;
	local_view_.lidar = &latest_lidar_;
	local_view_.alarm_vec = &latest_alarm_vec_;
}

/**
 * @brief Init-初始化函数
 *
 * 对控制模块中所使用的模块进行初始化和读取配置文件，函数功能如下：
 * 1. 读取control_conf.cfg配置文件中的内容；
 * 2. 轨迹分析器（TrajectoryAnalyzer）、车辆状态提供器（VehicleStateProvider）、
 *    纵向控制器（LonController）、横向控制器（LatController）、
 *    精准停车控制器（PreciseParkingController）、安全保护器（PreciseParkingController）
 *    等主要功能模块的初始化；
 * 3. 数据输入（Input）、数据输出（Output）、nanomsg通信（NanomsgCommunication）等通信
 *    模块初始化，每个模块都开启了一个线程。
 *
 * @note 任何一项数据读取失败或模块初始化失败，程序就直接退出。
 */
bool ControlComponent::Init() {
	//DLT log system init...
	DLT_REGISTER_APP("TAPP", "Test Application for Logging");
	DLT_REGISTER_CONTEXT(*dlt_ctx_, "TES1", "Test Context for Logging");
	DLT_REGISTER_CONTEXT_LL_TS(*dlt_ctx_, "TES1", " First context ",
			DLT_LOG_VERBOSE, DLT_TRACE_STATUS_OFF);

	// 读取control_conf.cfg配置文件中的内容
	if (!ReadControlConfig(control_config_)) {
		printf("@ReadControlConfig function "
				"read config parameters fail!!!@  \n");
		return false;
	} else {
		DltLogOutputConfig();
	}

	enable_precise_parking_control_ =
			control_config_->enable_precise_parking_control;
	enable_6666_port_receive_lidar_ =
			control_config_->enable_6666_port_receive_lidar;
	enable_AEB_protect_ =
			control_config_->safety_guardian_config.enable_AEB_protect;
	enable_lane_ditch_protect_ =
			control_config_->safety_guardian_config.enable_lane_ditch_protect;
	enable_safety_guardian_ =
			control_config_->safety_guardian_config.enable_safety_guardian;
	longitudinal_control_mode_ =
			control_config_->longitudinal_controller_config.longitudinal_control_mode;
	debug_.print_period_10ms = control_config_->print_period_10ms;
	steering_transmission_ratio_ =
			control_config_->lateral_controller_config.steering_transmission_ratio;

	// 轨迹分析器初始化
	if (!trajectory_analyzer_->Init(&debug_)) {
		printf("@trajectory_analyzer_->Init function execute fail!!!@  \n");
		return false;
	}
	// 车辆状态提供器初始化
	if (!vehicle_state_->Init()) {
		printf("@vehicle_state_->Init function execute fail!!!@  \n");
		return false;
	}
	// 纵向控制器初始化
	if (!longitudinal_controller_->Init(&debug_)) {
		printf("@longitudinal_controller_->Init function "
				"execute fail!!!@  \n");
		return false;
	}
	// 横向控制器初始化
	if (!lateral_controller_->Init(&debug_)) {
		printf("@lateral_controller_->Init function execute fail!!!@  \n");
		return false;
	}
	// 精准停车控制器初始化
//	if (enable_precise_parking_control_) {
//		precise_parking_controller_ =
//				std::make_shared<PreciseParkingController>(dlt_ctx_,
//						control_config_);
//		if (!precise_parking_controller_->Init(&debug_)) {
//			printf("@precise_parking_controller_->Init function "
//					"execute fail!!!@  \n");
//			return false;
//		}
//	}
	// 安全保护器初始化
	if (enable_safety_guardian_) {
		safety_guardian_ = std::make_shared<SafetyGuardian>(dlt_ctx_,
				control_config_);
		if (!safety_guardian_->Init(&debug_)) {
			printf("@safety_guardian_->Init function execute fail!!!@  \n");
			return false;
		}
	}

	// 数据输入模块初始化
	if (!input_->Start()) {
		printf("@input_->Start function Start fail!!!@  \n");
		return false;
	}
	// 数据输出模块初始化
	if (!output_->Start()) {
		printf("@output_->Start function Start fail!!!@  \n");
		return false;
	}
	// nanomsg通信模块初始化
	if (!nanomsg_communication_->Init(&debug_)) {
		printf("@nanomsg_communication_->Init function "
				"execute fail!!!@  \n");
		return false;
	}
	// [New] 初始化内部规划器
    local_planner_ = std::make_shared<tp::LocalPlanner>();

	// 加载地图数据 (假设地图文件放在可访问的路径下)
	std::vector<tp::TrajectoryData> maps;
	// 注意：请确保运行环境中有此 JSON 文件
	if (tp::JsonParser::loadTrajectories("./trajectories.json", maps)) {
	    local_planner_->importTrajectoryLibrary(maps);
	    printf("Internal Planner Initialized Successfully.\n");
	} else {
	    printf("@Error: Failed to load trajectory map for Internal Planner!@\n");
	    return false;
	}
	// [New] CSV 回放模式初始化
	std::string csv_route_file = "./planning_data.csv";

	if (LoadTrajectoryFromCSV(csv_route_file)) {
	    printf("Mode: CSV Playback Active. Route: %s\n", csv_route_file.c_str());
	} else {
	    printf("@Warning: Failed to load CSV route. Will revert to other modes.@\n");
	}
	return true;
}

/**
 * @brief Proc-功能处理函数
 *
 * 调用所有与控制相关的模块，实现控制功能，函数功能如下：
 * 1. 更新从网络报文中接收的定位、规划、底盘信息；
 * 2. 更新车辆状态，包括定位信息和底盘信息；
 * 3. 当有新规划数据接收后，更新轨迹信息，同时计算匹配点、预瞄点和最大曲率；
 * 4. 计算控制命令，得出发送给底盘所需的速度、油门刹车、转向等信息；
 * 5. 更新控制命令的发送信息，以备发送线程调用；
 * 6. nanomsg信息的发送，主要包括自动驾驶标志位、精准停车完成标志等信息。
 *
 * @note 该函数10ms执行周期，决定了控制周期。
 */
bool ControlComponent::Proc() {
	// 更新从网络报文中接收的定位、规划、底盘信息，自动驾驶启动时，若未启动，则直接返回
	if (!NetworkFrameInput()) {
		return false;
	}
	HostPCTrajectoryCommand host_pc_cmd = nanomsg_communication_->GetHostPCTrajectoryCommand();
	debug_.loop_period_count > 10000 ?
			debug_.loop_period_count = 0 : debug_.loop_period_count++;
	// 更新车辆状态，包括定位信息和底盘信息
	vehicle_state_->Update(&local_view_, control_command_.gear_command);
	// ==========================================
	// [New] 插入内部规划器逻辑
	// 这将根据当前 vehicle_state_ 生成新的 latest_trajectory_
	// ==========================================
	RunInternalPlanner();
	//if (!csv_global_path_.empty()) {
	     //RunCSVPlaybackPlanner(); // <--- 这里执行 CSV 数据注入
	//}
	// 当有新规划数据接收后，更新轨迹信息，同时计算匹配点、预瞄点和最大曲率
	trajectory_analyzer_->TrajectoryAnalyzerProcess(&local_view_,
			vehicle_state_, host_pc_cmd);
	// 计算控制命令，得出发送给底盘所需的速度、油门刹车、转向等信息
	ProduceControlCommand(&local_view_, vehicle_state_, &control_command_);

	/**/
//	if (host_pc_cmd.MpcCtrller >= 0)
//	{
//		control_command_.throttle_command = host_pc_cmd.MpcCtrller;
//		control_command_.brake_command = 0;
//	}
//	else
//	{
//		control_command_.throttle_command = 0;
//		control_command_.brake_command = -host_pc_cmd.MpcCtrller;
//	}
	/**/

	// 更新控制命令的发送信息，以备发送线程调用
	output_->ControlCommandUpdate(&control_command_);
	// nanomsg信息的发送，主要包括自动驾驶标志位、精准停车完成标志等信息
	nanomsg_communication_->task_sendnanomsg_entry(vehicle_state_, &debug_);
	// 打印DLT日志
	if (debug_.loop_period_count % debug_.print_period_10ms == 0) {
		DltLogOutput();
	}
	static int telemetry_count = 0;
	if (telemetry_count++ % 10 == 0) { // 每 10 * 10ms = 100ms 发布一次
		LongiTelemetryData telemetry_data = {0}; // 使用新的结构体，并初始化为0

		// 填充“四件套”数据
		telemetry_data.target_speed_ms = local_view_.matched_preview_point[0].trajectory_point.fSpeed;
		telemetry_data.actual_speed_ms = vehicle_state_->speed_feedback();
		telemetry_data.throttle_cmd = control_command_.throttle_command;
		telemetry_data.brake_cmd = control_command_.brake_command;
		telemetry_data.speed_filter_result_ms = longitudinal_controller_->get_speed_filter_result();
		// 通过反向Nanomsg通道发送出去
		if (local_view_.localization != nullptr) {
			telemetry_data.rtk_lat = local_view_.localization->strImu.dLatitude;
			telemetry_data.rtk_lon = local_view_.localization->strImu.dLongitude;
		} else {
			telemetry_data.rtk_lat = 0.0;
			telemetry_data.rtk_lon = 0.0;
		}
		nanomsg_communication_->PublishTelemetry(telemetry_data);
	}
	return true;
}

bool ControlComponent::NetworkFrameInput() {
	// 更新从网络报文中接收的定位、规划、底盘信息，自动驾驶启动时，若未启动，则直接返回
	if (!input_->GetLocationFrame(&latest_localization_)) {
		static int receive_frame_count = 0;
		receive_frame_count++;
		if ((receive_frame_count % 50) == 0) {
			printf("@%d@ receive Location fail !!!  \n", receive_frame_count);
		}
		return false;
	}
	if (!input_->GetPlanningFrame(&latest_trajectory_)) {
		static int receive_frame_count = 0;
		receive_frame_count++;
		if ((receive_frame_count % 50) == 0) {
			printf("$%d$ receive planning fail !!!  \n", receive_frame_count);
		}
		return false;
	}
	if (!input_->GetCarStatusFrame(&latest_chassis_)) {
		static int receive_frame_count = 0;
		receive_frame_count++;
		if ((receive_frame_count % 50) == 0) {
			printf("#%d# receive carstatus fail !!!  \n", receive_frame_count);
		}
		return false;
	}

	if (enable_AEB_protect_) {
		if (!input_->GetLidarFrame(&latest_lidar_)) {
			static int receive_frame_count = 0;
			receive_frame_count++;
			if ((receive_frame_count % 50) == 0) {
				printf("@%d@ receive Lidar fail !!!  \n", receive_frame_count);
			}
			return false;
		} else {
//			printf(" receive Lidar successful !!!  \n");
		}
	}
	if (enable_6666_port_receive_lidar_) {
		if (!input_->GetLocMarkFrame(&latest_loc_mark_)) {
			static int receive_frame_count = 0;
			receive_frame_count++;
			if ((receive_frame_count % 50) == 0) {
				printf("@%d@ receive LocMark fail !!!  \n",
						receive_frame_count);
			}
			return false;
		}
	}
	if (enable_lane_ditch_protect_) {
		if (!input_->GetLaneDitchFrame(&latest_lane_ditch_)) {
			static int receive_frame_count = 0;
			receive_frame_count++;
			if ((receive_frame_count % 50) == 0) {
				printf("@%d@ receive LaneDitch fail !!!  \n",
						receive_frame_count);
			}
			return false;
		}
	}
	if (!input_->GetAlarmFrame(latest_alarm_vec_)) {
		static int receive_frame_count = 0;
		receive_frame_count++;
		if ((receive_frame_count % 50) == 0) {
			printf("@%d@ receive Alarm fail !!!  \n", receive_frame_count);
		}
		return false;
	}
	return true;
}

/**
 * @brief ProduceControlCommand-生成控制命令函数
 *
 * 主要用于产生最终的速度、油门、刹车、转向等控制命令，函数功能如下：
 * 1. 纵向控制器，用于产生油门、刹车、速度控制命令；
 * 2. 横向控制器，用于产生转向控制命令；
 * 3. 精准停车控制器，在精准停车阶段，更新速度、转向命令，以更精准的控制位置和航向角；
 * 4. 安全保护模块，设计了若干种故障保护，确保自动驾驶的安全性；
 * 5. 产生其他控制命令，如转向灯、驻车等。
 *
 * @note 纵向控制器和横向控制器产生的命令，可能会被精准停车和安全保护模块重新更新。
 */
void ControlComponent::ProduceControlCommand(const LocalView* local_view,
		const std::shared_ptr<VehicleStateProvider> vehicle_state,
		ControlCommand* control_command) {
	st_ecu_info_nm nanomsg_command_from_remote =
			nanomsg_communication_->GetRemoteNanomsgCommand();
	if (vehicle_state->drive_mode_feedback() == COMPLETE_AUTO_DRIVE) {
		if ((nanomsg_command_from_remote.driveMode == COMPLETE_MANUAL)
				&& is_vehicle_remote_mode_) {
			control_command->gear_command = N;
			control_command->throttle_command = 0.0;
			control_command->brake_command = 0.0;
			control_command->steer_command = 0.0;
			control_command->speed_command = 0.0;
			control_command->acc_command = 0.0;
		} else if (nanomsg_command_from_remote.driveMode == REMOTE_CONTROL) {
			is_vehicle_remote_mode_ = true;
			control_command->gear_command =
					(Gear) nanomsg_command_from_remote.gear;
			control_command->throttle_command =
					nanomsg_command_from_remote.throttle;
			control_command->brake_command = nanomsg_command_from_remote.brake;
			control_command->steer_command = nanomsg_command_from_remote.angle;
			control_command->speed_command = nanomsg_command_from_remote.speed;
			control_command->acc_command = nanomsg_command_from_remote.ACC;
		} else {
			is_vehicle_remote_mode_ = false;
		}
	} else {
		is_vehicle_remote_mode_ = false;
		control_command->throttle_command = 0.0;
		control_command->brake_command = 0.0;
		control_command->steer_command = 0.0;
		control_command->speed_command = 0.0;
		control_command->acc_command = 0.0;
	}
	if (!is_vehicle_remote_mode_) {
		// 纵向控制器，用于产生油门、刹车、速度控制命令
		longitudinal_controller_->LonControllerControlCommandCompute(local_view,
				vehicle_state, control_command);
		// 横向控制器，用于产生转向控制命令
		lateral_controller_->LatControllerControlCommandCompute(local_view,
				vehicle_state, control_command);
		// 精准停车控制器，在精准停车阶段，更新速度、转向命令，以更精准的控制位置和航向角
//		if (enable_precise_parking_control_) {
//			precise_parking_controller_->PreciseParkingControlCommandUpdate(
//					local_view, vehicle_state, control_command);
//		}
		// 安全保护模块，设计了若干种故障保护，确保自动驾驶的安全性
		if (enable_safety_guardian_) {
			safety_guardian_->SafetyGuardianControlCommandUpdate(local_view,
					vehicle_state, control_command);
		}
		// 产生其他控制命令，如转向灯、驻车等
		OtherControlCommandCompute(local_view, vehicle_state, control_command);
	}
	//更新心跳，线控程序会检测此心跳，确保控制命令在正常更新
	static uc_int32_t heart_command = 0;
	heart_command > 255 ? heart_command = 0 : heart_command++;
	control_command->heart_command = heart_command & 0xFF;
}

/**
 * @brief UpdateGearCommand-生成档位命令函数
 *
 * 当处于油门刹车控制模式时，采用nanomsg通信接收规划下发的档位。
 *
 * @note 无。
 */
void ControlComponent::UpdateGearCommand(ControlCommand* control_command,
		const std::shared_ptr<VehicleStateProvider> vehicle_state) {
	// 通过nanomsg接收规划下发的档位信息，并更新档位
	if (strcmp(longitudinal_control_mode_, "throttle_brake") == 0) {
		st_ecu_info_nm nanomsg_command_from_planning =
				nanomsg_communication_->GetEcuNanomsgCommand();

		nanomsg_plan_gear_ = nanomsg_command_from_planning.gear;
		char gear = nanomsg_plan_gear_;
		if (vehicle_state->gear_feedback() != nanomsg_plan_gear_) {
			// 切换档位时，踩刹车
			control_command->brake_command = 70;
			control_command->throttle_command = 0.0;
			if (fabs(vehicle_state->speed_feedback()) < 0.1) {
				;
			} else {
				gear = vehicle_state->gear_feedback();
			}
		}
		if (gear == 2) {
			control_command->gear_command = D;
		} else if (gear == 1) {
			control_command->gear_command = R;
		} else {
			control_command->gear_command = N;
		}

		nanomsg_io_control_ = nanomsg_command_from_planning.bitEcu;
		if ((nanomsg_io_control_ & 0x80000) == 0x80000) {
			control_command->light_command.door = 1;
		} else if ((nanomsg_io_control_ & 0x100000) == 0x100000) {
			control_command->light_command.door = 2;
		} else {
			control_command->light_command.door = 0;
		}
	}

	if (strcmp(longitudinal_control_mode_, "acceleration_brake") == 0) {
		st_ecu_info_nm nanomsg_command_from_planning =
				nanomsg_communication_->GetEcuNanomsgCommand();

		nanomsg_plan_gear_ = nanomsg_command_from_planning.gear;
		char gear = nanomsg_plan_gear_;
		if (vehicle_state->gear_feedback() != nanomsg_plan_gear_) {
			// 切换档位时，踩刹车
			if (vehicle_state->gear_feedback() == D) {
				control_command->acc_command = -1.5;
			} else if (vehicle_state->gear_feedback() == R) {
				control_command->acc_command = 1.5;
			} else {
				control_command->acc_command = 0.0;
			}
			if (fabs(vehicle_state->speed_feedback()) < 0.1) {
				;
			} else {
				gear = vehicle_state->gear_feedback();
			}
		}
		if (gear == 2) {
			control_command->gear_command = D;
		} else if (gear == 1) {
			control_command->gear_command = R;
		} else {
			control_command->gear_command = N;
		}

		nanomsg_io_control_ = nanomsg_command_from_planning.bitEcu;
		if ((nanomsg_io_control_ & 0x80000) == 0x80000) {
			control_command->light_command.door = 1;
		} else if ((nanomsg_io_control_ & 0x100000) == 0x100000) {
			control_command->light_command.door = 2;
		} else {
			control_command->light_command.door = 0;
		}
	}
}

/**
 * @brief UpdateLightCommand-生成转向灯命令函数
 *
 * 主要使用轨迹的最大曲率和档位产生转向灯控制命令。
 *
 * @note 最大曲率的阈值可根据现场需求修改。
 */
void ControlComponent::UpdateLightCommand(ControlCommand* control_command) {
	double tyre_steer_angle = control_command->steer_command
			/ steering_transmission_ratio_;

	if (max_kappa_ > 0.01) {
		if (control_command->gear_command == Gear::D) {
			control_command->light_command.left_turnlight = 0;
			control_command->light_command.right_turnlight = 1;
			if (fabs(mp_point_[0].trajectory_point.fKappa) > 0.01) {
				if (tyre_steer_angle > 0.0) {
					control_command->light_command.left_turnlight = 1;
					control_command->light_command.right_turnlight = 0;
				}
				if (tyre_steer_angle < 0.0) {
					control_command->light_command.left_turnlight = 0;
					control_command->light_command.right_turnlight = 1;
				}
			}
		}
		if (control_command->gear_command == Gear::R) {
			control_command->light_command.left_turnlight = 1;
			control_command->light_command.right_turnlight = 0;
			if (fabs(mp_point_[0].trajectory_point.fKappa) > 0.01) {
				if (tyre_steer_angle > 0.0) {
					control_command->light_command.left_turnlight = 0;
					control_command->light_command.right_turnlight = 1;
				}
				if (tyre_steer_angle < 0.0) {
					control_command->light_command.left_turnlight = 1;
					control_command->light_command.right_turnlight = 0;
				}
			}
		}
	} else if (max_kappa_ < -0.01) {
		if (control_command->gear_command == Gear::D) {
			control_command->light_command.left_turnlight = 1;
			control_command->light_command.right_turnlight = 0;
			if (fabs(mp_point_[0].trajectory_point.fKappa) > 0.01) {
				if (tyre_steer_angle > 0.0) {
					control_command->light_command.left_turnlight = 1;
					control_command->light_command.right_turnlight = 0;
				}
				if (tyre_steer_angle < 0.0) {
					control_command->light_command.left_turnlight = 0;
					control_command->light_command.right_turnlight = 1;
				}
			}
		}
		if (control_command->gear_command == Gear::R) {
			control_command->light_command.left_turnlight = 0;
			control_command->light_command.right_turnlight = 1;
			if (fabs(mp_point_[0].trajectory_point.fKappa) > 0.01) {
				if (tyre_steer_angle > 0.0) {
					control_command->light_command.left_turnlight = 0;
					control_command->light_command.right_turnlight = 1;
				}
				if (tyre_steer_angle < 0.0) {
					control_command->light_command.left_turnlight = 1;
					control_command->light_command.right_turnlight = 0;
				}
			}
		}
	} else {
		control_command->light_command.left_turnlight = 0;
		control_command->light_command.right_turnlight = 0;
	}
}

/**
 * @brief OtherControlCommandCompute-生成其他控制命令函数
 *
 * 主要用于产生除速度、油门、刹车、转向外的其他控制命令，函数功能如下：
 * 1. 灯光控制命令，转向灯、大灯、双闪等在这里处理；
 * 2. 其他控制命令还未加，如驻车、空调、车门等，这些待扩展。
 *
 * @note 无。
 */
void ControlComponent::OtherControlCommandCompute(const LocalView* local_view,
		const std::shared_ptr<VehicleStateProvider> vehicle_state,
		ControlCommand* control_command) {
	// 灯光控制命令，转向灯、大灯、双闪等在这里处理
	UpdateLightCommand(control_command);
	// 更新档位命令
	UpdateGearCommand(control_command, vehicle_state);
}

void ControlComponent::DltLogOutputConfig() {
	DLT_LOG(*dlt_ctx_, DLT_LOG_INFO, DLT_STRING("@Controller@"),
			DLT_STRING("enable_precise_parking_control:"),
			DLT_INT32(control_config_->enable_precise_parking_control),
			DLT_STRING("enable_6666_port_receive_lidar:"),
			DLT_INT32(control_config_->enable_6666_port_receive_lidar),
			DLT_STRING("print_period_10ms:"),
			DLT_INT32(control_config_->print_period_10ms),
			DLT_STRING("\n @SafetyGuardian@"),
			DLT_STRING("enable_safety_guardian:"),
			DLT_INT32(control_config_->safety_guardian_config.enable_safety_guardian),
			DLT_STRING("safety_guardian_separate_enable:"),
			DLT_STRING(control_config_->safety_guardian_config.safety_guardian_separate_enable),
			DLT_STRING("enable_AEB_protect:"),
			DLT_INT32(control_config_->safety_guardian_config.enable_AEB_protect),
			DLT_STRING("enable_lane_ditch_protect:"),
			DLT_INT32(control_config_->safety_guardian_config.enable_lane_ditch_protect),
			DLT_STRING("trajectory_received_timeout_threshold:"),
			DLT_INT32(control_config_->safety_guardian_config.trajectory_received_timeout_threshold),
			DLT_STRING("localization_received_timeout_threshold:"),
			DLT_INT32(control_config_->safety_guardian_config.localization_received_timeout_threshold),
			DLT_STRING("chassis_received_timeout_threshold:"),
			DLT_INT32(control_config_->safety_guardian_config.chassis_received_timeout_threshold),
			DLT_STRING("lateral_error_over_threshold:"),
			DLT_FLOAT64(control_config_->safety_guardian_config.lateral_error_over_threshold),
			DLT_STRING("pure_delay_link_time_constant:"),
			DLT_FLOAT64(control_config_->safety_guardian_config.pure_delay_link_time_constant),
			DLT_STRING("inertial_link_time_constant:"),
			DLT_FLOAT64(control_config_->safety_guardian_config.inertial_link_time_constant),
			DLT_STRING("vehicle_minimum_radius:"),
			DLT_FLOAT64(control_config_->safety_guardian_config.vehicle_minimum_radius),
			DLT_STRING("trajectory_rationality_distance_limited:"),
			DLT_FLOAT64(control_config_->safety_guardian_config.trajectory_rationality_distance_limited));

	DLT_LOG(*dlt_ctx_, DLT_LOG_INFO, DLT_STRING("\n @LongitudinalController@"),
			DLT_STRING("longitudinal_control_mode:"),
			DLT_STRING(control_config_->longitudinal_controller_config.longitudinal_control_mode),
			DLT_STRING("is_chassis_contain_gear:"),
			DLT_INT32(control_config_->longitudinal_controller_config.is_chassis_contain_gear),
			DLT_STRING("brake_maximum_limited:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.brake_maximum_limited),
			DLT_STRING("throttle_maximum_limited:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.throttle_maximum_limited),
			DLT_STRING("enable_safety_speed_protect:"),
			DLT_INT32(control_config_->longitudinal_controller_config.pure_speed_controller_config.enable_safety_speed_protect),
			DLT_STRING("\n @BasedPreviewPidController@"),
			DLT_STRING("plan_dec_preview_point:"),
			DLT_INT32(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.plan_dec_preview_point),
			DLT_STRING("plan_updown_preview_point:"),
			DLT_INT32(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.plan_updown_preview_point),
			DLT_STRING("plan_acc_preview_point:"),
			DLT_INT32(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.plan_acc_preview_point),
			DLT_STRING("plan_speed_stable_preview_point:"),
			DLT_INT32(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.plan_speed_stable_preview_point),
			DLT_STRING("plan_speed_stable_estimate_point_num:"),
			DLT_INT32(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.plan_speed_stable_estimate_point_num),
			DLT_STRING("plan_speed_stable_boundary_cond:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.plan_speed_stable_boundary_cond),
			DLT_STRING("plan_up_slop_boundary_cond:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.plan_up_slop_boundary_cond),
			DLT_STRING("plan_down_slop_boundary_cond:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.plan_down_slop_boundary_cond),
			DLT_STRING("start_init_value:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.start_init_value),
			DLT_STRING("start_integral_sat_value:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.start_integral_sat_value),
			DLT_STRING("start_acc_coeff:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.start_acc_coeff),
			DLT_STRING("park_init_value:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.park_init_value),
			DLT_STRING("park_comfort_coeff:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.park_comfort_coeff),
			DLT_STRING("module_stable_test_speed:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.module_stable_test_speed),
			DLT_STRING("module_thr_test_value:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.module_thr_test_value),
			DLT_STRING("module_thr_acc_time:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.module_thr_acc_time),
			DLT_STRING("module_integral_time:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.module_integral_time),
			DLT_STRING("module_bra_deadzone_value:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.module_bra_deadzone_value));

	DLT_LOG(*dlt_ctx_, DLT_LOG_INFO, DLT_STRING("module_free_acc_value:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.module_free_acc_value),
			DLT_STRING("module_bra_acc_max_value:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.module_bra_acc_max_value),
			DLT_STRING("module_slop_calibration_value:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.module_slop_calibration_value),
			DLT_STRING("slop_compen_regulation_ratio:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.slop_compen_regulation_ratio),
			DLT_STRING("car_dec_safe_dis:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.module_bra_acc_max_value),

			DLT_STRING("kd_pid:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.kd_pid),

			DLT_STRING("feedforward_kv:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.feedforward_kv),

			DLT_STRING("feedforward_ka:"),
			DLT_FLOAT64(control_config_->longitudinal_controller_config.based_preview_pid_controller_config.feedforward_ka),

			DLT_STRING("\n @LongitudinalController@"),
			DLT_STRING("lateral_control_mode:"),
			DLT_STRING(control_config_->lateral_controller_config.lateral_control_mode),
			DLT_STRING("riccati_equation_solve_method:"),
			DLT_INT32(control_config_->lateral_controller_config.riccati_equation_solve_method),
			DLT_STRING("steering_pattern:"),
			DLT_INT32(control_config_->lateral_controller_config.steering_pattern),
			DLT_STRING("enable_kappa_and_heading_angle_compute:"),
			DLT_INT32(control_config_->lateral_controller_config.enable_kappa_and_heading_angle_compute),
			DLT_STRING("steering_maximum_limited:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.steering_maximum_limited),
			DLT_STRING("steering_transmission_ratio:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.steering_transmission_ratio),
			DLT_STRING("preview_point_num:"),
			DLT_INT32(control_config_->lateral_controller_config.preview_point_num),
			DLT_STRING("enable_distance_preview:"),
			DLT_INT32(control_config_->lateral_controller_config.enable_distance_preview),
			DLT_STRING("lock_steer_speed:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.lock_steer_speed),
			DLT_STRING("ts:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.ts),
			DLT_STRING("cf:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.cf),
			DLT_STRING("cr:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.cr),
			DLT_STRING("mass_fl:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.mass_fl),
			DLT_STRING("mass_fr:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.mass_fr),
			DLT_STRING("mass_rl:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.mass_rl),
			DLT_STRING("mass_rr:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.mass_rr),
			DLT_STRING("wheelbase:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.wheelbase),
			DLT_STRING("eps:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.eps));

	DLT_LOG(*dlt_ctx_, DLT_LOG_INFO, DLT_STRING("matrix_q1:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.matrix_q1),
			DLT_STRING("matrix_q2:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.matrix_q2),
			DLT_STRING("matrix_q3:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.matrix_q3),
			DLT_STRING("matrix_q4:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.matrix_q4),
			DLT_STRING("max_iteration:"),
			DLT_INT32(control_config_->lateral_controller_config.max_iteration),
			DLT_STRING("reverse_steer_ratio_compensate:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.reverse_steer_ratio_compensate),
			DLT_STRING("enable_maximum_steer_rate_limited:"),
			DLT_INT32(control_config_->lateral_controller_config.enable_maximum_steer_rate_limited),
			DLT_STRING("max_steer_angle_rate:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.max_steer_angle_rate),
			DLT_STRING("enable_max_lateral_acceleration_limited:"),
			DLT_INT32(control_config_->lateral_controller_config.enable_max_lateral_acceleration_limited),
			DLT_STRING("max_lateral_acceleration:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.max_lateral_acceleration),
			DLT_STRING("enable_steer_mrac_control:"),
			DLT_INT32(control_config_->lateral_controller_config.enable_steer_mrac_control),
			DLT_STRING("enable_look_ahead_back_control:"),
			DLT_INT32(control_config_->lateral_controller_config.enable_look_ahead_back_control),
			DLT_STRING("lookahead_station:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.lookahead_station),
			DLT_STRING("lookback_station:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.lookback_station),
			DLT_STRING("lookahead_station_high_speed:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.lookahead_station_high_speed),
			DLT_STRING("lookback_station_high_speed:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.lookback_station_high_speed),
			DLT_STRING("enable_reverse_leadlag_compensation:"),
			DLT_INT32(control_config_->lateral_controller_config.enable_reverse_leadlag_compensation),
			DLT_STRING("\n @ReverseLeadlagController@"),
			DLT_STRING("innerstate_saturation_level:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.reverse_leadlag_config.innerstate_saturation_level),
			DLT_STRING("alpha:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.reverse_leadlag_config.alpha),
			DLT_STRING("beta:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.reverse_leadlag_config.beta),
			DLT_STRING("tau:"),
			DLT_FLOAT64(control_config_->lateral_controller_config.reverse_leadlag_config.tau));
}
/**
 * @brief ReadControlConfig-读取控制配置文件函数
 *
 * 用于读取control_conf.cfg配置文件中的内容，函数功能如下：
 * 1. 配置文件主要分为三部分，纵向相关、横向相关、安全保护相关。
 *
 * @note 为与之前的旧版本区分，配置文件的文件夹命名为control_new。
 */
bool ControlComponent::ReadControlConfig(
		std::shared_ptr<ControlConfig> control_config) {
	config_t strCfg;
	config_init(&strCfg);

	if (!config_read_file(&strCfg, CONTROL_CONFIG_FILE)) {
		fprintf(stderr, "%s:%d - %s\n", config_error_file(&strCfg),
				config_error_line(&strCfg), config_error_text(&strCfg));
		config_destroy(&strCfg);
		return false;
	}

	config_setting_t *pSetting;
	pSetting = config_lookup(&strCfg, "Controller");
// 使能精准停车控制，bool类型；true:使能，false:失能
	if (pSetting != NULL) {
		if (!(config_setting_lookup_bool(pSetting,
				"enable_precise_parking_control",
				&control_config->enable_precise_parking_control))) {
			printf("@enable_precise_parking_control@ read failed!!! \n");
			return false;
		} else {
			printf("enable_precise_parking_control:%d \n\n",
					control_config->enable_precise_parking_control);
		}
		if (!(config_setting_lookup_bool(pSetting,
				"enable_6666_port_receive_lidar",
				&control_config->enable_6666_port_receive_lidar))) {
			printf("@enable_6666_port_receive_lidar@ read failed!!! \n");
			return false;
		} else {
			printf("enable_6666_port_receive_lidar:%d \n\n",
					control_config->enable_6666_port_receive_lidar);
		}

		if (!(config_setting_lookup_int(pSetting, "print_period_10ms",
				&control_config->print_period_10ms))) {
			printf("@print_period_10ms@ read failed!!! \n");
			return false;
		} else {
			printf("print_period_10ms:%d \n",
					control_config->print_period_10ms);
		}
	} else {
		printf("config_lookup Controller failed!!! \n\n");
		return false;
	}

// 读取纵向相关的配置信息
	if (!ReadLongitudinalControlConfig(&strCfg, control_config)) {
		printf("@ReadLongitudinalControlConfig function "
				"read config parameters fail!!!@  \n");
		return false;
	}
// 读取横向相关的配置信息
	if (!ReadLateralControlConfig(&strCfg, control_config)) {
		printf("@ReadLateralControlConfig function "
				"read config parameters fail!!!@  \n");
		return false;
	}
// 读取安全保护相关的配置信息
	if (!ReadSafetyGuardianConfig(&strCfg, control_config)) {
		printf("@ReadLateralControlConfig function "
				"read config parameters fail!!!@  \n");
		return false;
	}
	return true;
}

/**
 * @brief DltLogOutput-DLT日志输出函数
 *
 * 用于打印ControlComponent类中相关日志输出，以备调试；
 *
 * @note 无。
 */
void ControlComponent::DltLogOutput() {
	uc_uint64_t current_time = time_now_us();
	static uc_uint64_t last_current_time = 0; //current_time;
	uc_uint64_t loop_period_us = llabs(current_time - last_current_time);
	last_current_time = current_time;

	printf(
			"control_command_.steer_command:%lf,vehicle_state_->steer_feedback():%lf \n",
			control_command_.steer_command, vehicle_state_->steer_feedback());
	DLT_LOG(*dlt_ctx_, DLT_LOG_INFO,
			DLT_STRING("@ControlComponent1_V1.01.02_2@"),
			DLT_STRING("loop_period_us:"), DLT_UINT64(loop_period_us),
			DLT_STRING("current_time:"), DLT_UINT64(current_time),

			DLT_STRING("drive_mode_feedback:"),
			DLT_INT32(vehicle_state_->drive_mode_feedback()),

			DLT_STRING("speed:"), DLT_FLOAT64(control_command_.speed_command),
			DLT_STRING(":"), DLT_FLOAT64(mp_point_[0].trajectory_point.fSpeed),
			DLT_STRING(":"), DLT_FLOAT64(vehicle_state_->speed_feedback()),

			DLT_STRING("gear:"), DLT_INT32(control_command_.gear_command),
			DLT_STRING(":"), DLT_INT32(nanomsg_plan_gear_), DLT_STRING(":"),
			DLT_INT32(vehicle_state_->gear_feedback()),

			DLT_STRING("throttle:"),
			DLT_FLOAT64(control_command_.throttle_command), DLT_STRING(":"),
			DLT_FLOAT64(vehicle_state_->throttle_feedback()),

			DLT_STRING("brake:"), DLT_FLOAT64(control_command_.brake_command),
			DLT_STRING(":"), DLT_FLOAT64(vehicle_state_->brake_feedback()),

			DLT_STRING("front_steer:"),
			DLT_FLOAT64(control_command_.steer_command), DLT_STRING(":"),
			DLT_FLOAT64(vehicle_state_->steer_feedback()),

			DLT_STRING("EPB:"), DLT_INT32(control_command_.EPB_command),
			DLT_STRING(":"), DLT_INT32(vehicle_state_->EPB_feedback()),

			DLT_STRING("soc:"), DLT_INT32(vehicle_state_->soc_feedback()),

			DLT_STRING("bit_feedback:"), DLT_HEX32(nanomsg_io_control_),
			DLT_HEX32(control_command_.light_command.door),
			DLT_HEX32(vehicle_state_->bit_feedback()),

			DLT_STRING("acc:"), DLT_FLOAT64(control_command_.acc_command),
			DLT_STRING(":"), DLT_FLOAT64(vehicle_state_->acc_feedback()),

			DLT_STRING("x:"), DLT_FLOAT64(vehicle_state_->x()),
			DLT_STRING("y:"), DLT_FLOAT64(vehicle_state_->y()),

			DLT_STRING("heading_rad:"),
			DLT_FLOAT64(vehicle_state_->heading_rad()),
			DLT_STRING("angular_velocity_rad:"),
			DLT_FLOAT64(vehicle_state_->angular_velocity_rad()),
			DLT_STRING("pitch_angle:"),
			DLT_FLOAT64(vehicle_state_->pitch_angle()), DLT_STRING("laneid:"),
			DLT_INT32((int)(latest_trajectory_.pstrPlanning[3].fDisplace)),
			DLT_STRING("is_vehicle_remote_mode:"),
			DLT_INT32(is_vehicle_remote_mode_));
}
void ControlComponent::RunInternalPlanner() {
    if (!local_planner_ || !vehicle_state_) return;

    // ==========================================
    // 1. 输入转换：VehicleStateProvider -> tp::Vehicle
    // ==========================================

    // 获取车辆当前状态
    double current_x = vehicle_state_->x();
    double current_y = vehicle_state_->y();
    double current_speed = vehicle_state_->speed_feedback();
    double current_heading = vehicle_state_->heading_rad(); // 弧度

    // 构建 tp::Vehicle 对象
    // 注意：Control模块是2D平面，Z轴设为0
    tp::Point start_pos(current_x, current_y, 0.0);
    tp::Vehicle tp_vehicle(start_pos);

    tp_vehicle.speed = current_speed;

    // 计算前向向量 (基于航向角)
    tp_vehicle.forward_vec = tp::Vector(cos(current_heading), sin(current_heading), 0.0);
    tp_vehicle.velocity = tp_vehicle.forward_vec * current_speed;

    // ==========================================
    // 2. 执行规划
    // ==========================================
    tp::Trajectory path = local_planner_->generateLocalPath(tp_vehicle);

    // ==========================================
    // 3. 输出转换：tp::Trajectory -> STR_PLANNING_DATA
    // ==========================================

    // 获取指向 latest_trajectory_ 的指针 (这是 local_view_.trajectory 指向的对象)
    STR_PLANNING_DATA* output_traj = &latest_trajectory_;

    // 限制最大点数为 50 (TRAJECTORY_ARRAY_SIZE)
    int point_count = path.getPointCount();
    if (point_count > 50) point_count = 50;

    output_traj->iCounts = point_count;
    output_traj->ullTimestampModule = time_now_us(); // 更新时间戳

    for (int i = 0; i < point_count; ++i) {
        const auto& src_pt = path[i];
        auto& dst_pt = output_traj->pstrPlanning[i];

        // 坐标转换
        dst_pt.strPoint3f.fX = src_pt.position.x();
        dst_pt.strPoint3f.fY = src_pt.position.y();
        dst_pt.strPoint3f.fZ = 0.0;

        // 角度转换：tp使用弧度，Control模块通常使用角度(度)
        // 注意：TrajectoryAnalyzer::HeadingAngle 中看到使用了 * 180 / M_PI，说明内部使用角度制
        dst_pt.fTheta = src_pt.heading * 180.0 / M_PI;

        // 其他属性
        dst_pt.fKappa = src_pt.curvature;
        dst_pt.fSpeed = src_pt.speed;
        dst_pt.fAcc = src_pt.acceleration;
        dst_pt.fRelative_time = src_pt.relative_time;
        dst_pt.fDisplace = src_pt.arc_length;
    }

    // [可选] 打印调试信息
    // printf("Planner Update: x=%.2f, y=%.2f, pts=%d\n", current_x, current_y, point_count);
}
/**
 * 只提取 Point_Index == 0 的点（如果每次采样都是从车当前位置开始），这样连接起来就是车辆实际跑过的轨迹。
 */
bool ControlComponent::LoadTrajectoryFromCSV(const std::string& file_path) {
    csv_global_path_.clear();
    std::ifstream file(file_path);
    if (!file.is_open()) {
        printf("@Error: Failed to open CSV file: %s@\n", file_path.c_str());
        return false;
    }

    std::string line;
    // 跳过表头
    std::getline(file, line);

    while (std::getline(file, line)) {
        std::stringstream ss(line);
        std::string cell;
        std::vector<std::string> row;

        while (std::getline(ss, cell, ',')) {
            row.push_back(cell);
        }

        // 确保行数据足够 (基于 SaveToCSV_Debug 的列数，至少要有10列以上)
        if (row.size() < 12) continue;

        // 关键逻辑：只读取 index 为 0 的点，去除重复的规划帧，串联成一条长轨迹
        // CSV列索引参考: 0:Time, 1:Frame, 2:Index, 3:X, 4:Y, 5:Z, 6:Theta, 7:Kappa, 8:Speed, 9:Acc ...
        int point_index = std::stoi(row[2]);

        // 如果您提供的 CSV 是手动制作的纯路径点（没有重复帧），请注释掉下面这行判断
        if (point_index != 0) continue;

        STR_PLANNING pt;
        // 数据类型转换
        try {
            pt.strPoint3f.fX = std::stof(row[3]);
            pt.strPoint3f.fY = std::stof(row[4]);
            pt.strPoint3f.fZ = std::stof(row[5]);
            pt.fTheta        = std::stof(row[6]);
            pt.fKappa        = std::stof(row[7]);
            pt.fSpeed        = std::stof(row[8]); // 这里直接使用当时记录的速度
            pt.fAcc          = std::stof(row[9]);
            // 相对时间和距离在回放时需要根据当前车位置动态重算，这里先存原始值
            pt.fRelative_time = 0.0;
            pt.fDisplace      = 0.0;
        } catch (...) {
            continue; // 解析失败跳过
        }

        csv_global_path_.push_back(pt);
    }

    printf("CSV Trajectory Loaded Successfully. Total Points: %lu\n", csv_global_path_.size());
    return !csv_global_path_.empty();
}

/**
 * @brief 根据车辆当前位置，从长轨迹中截取50个点
 */
void ControlComponent::RunCSVPlaybackPlanner() {
    if (csv_global_path_.empty() || !vehicle_state_) return;

    // 1. 寻找最近点 (匹配车辆当前位置)
    double min_dist_sq = std::numeric_limits<double>::max();
    size_t closest_idx = 0;
    double car_x = vehicle_state_->x();
    double car_y = vehicle_state_->y();

    // 优化：如果在运动中，可以从上一帧的索引附近开始搜，这里为了简单直接全搜
    for (size_t i = 0; i < csv_global_path_.size(); ++i) {
        double dx = csv_global_path_[i].strPoint3f.fX - car_x;
        double dy = csv_global_path_[i].strPoint3f.fY - car_y;
        double dist_sq = dx * dx + dy * dy;
        if (dist_sq < min_dist_sq) {
            min_dist_sq = dist_sq;
            closest_idx = i;
        }
    }

    // 2. 填充 latest_trajectory_
    STR_PLANNING_DATA* output_traj = &latest_trajectory_;
    output_traj->ullTimestampModule = time_now_us();
    output_traj->iCounts = 50;

    double accumulated_s = 0.0;
    double accumulated_t = 0.0;

    for (int i = 0; i < 50; ++i) {
        // 防止索引越界：如果到了终点，就一直重复最后一个点
        size_t current_idx = closest_idx + i;
        if (current_idx >= csv_global_path_.size()) {
            current_idx = csv_global_path_.size() - 1;
        }

        auto& src_pt = csv_global_path_[current_idx];
        auto& dst_pt = output_traj->pstrPlanning[i];

        // 复制基础属性
        dst_pt = src_pt;

        // 3. 动态重算 S 和 T (这对于控制器的前馈非常重要)
        if (i > 0) {
            auto& prev_pt = output_traj->pstrPlanning[i - 1];
            double ds = sqrt(pow(dst_pt.strPoint3f.fX - prev_pt.strPoint3f.fX, 2) +
                             pow(dst_pt.strPoint3f.fY - prev_pt.strPoint3f.fY, 2));
            accumulated_s += ds;

            // dt = ds / v (防止除0)
            double v = std::max(fabs(src_pt.fSpeed), 0.1f);
            accumulated_t += ds / v;
        } else {
            // 第一个点（最近点）的 S 设为 0
            accumulated_s = 0.0;
            accumulated_t = 0.0;
        }

        dst_pt.fDisplace = accumulated_s;
        dst_pt.fRelative_time = accumulated_t;
    }
}
/*******************************end*****************************************/
