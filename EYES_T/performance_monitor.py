import os
import csv
import time
from datetime import datetime
from typing import Optional

try:
    import psutil  # type: ignore
except Exception:
    psutil = None

try:
    import GPUtil  # type: ignore
except Exception:
    GPUtil = None


class PerformanceMonitor:
    """
    轻量级性能监控器：
    - 记录 OCR/总处理时间、FPS、CPU/内存/GPU（可选）使用率
    - 每次运行可生成独立 CSV 日志，供汇总报告工具使用
    """

    def __init__(self, module_name: str, log_dir: str = "performance_logs", enable_gpu_monitor: bool = True):
        self.module_name = module_name
        self.log_dir = log_dir
        self.enable_gpu_monitor = enable_gpu_monitor and GPUtil is not None
        self._process = psutil.Process() if psutil else None
        if self._process and hasattr(self._process, "cpu_percent"):
            # 首次调用用于建立基线，避免第一次读取为0
            self._process.cpu_percent(None)
        self._run_started = False
        self.reset()

    def reset(self) -> None:
        self.ocr_times = []
        self.ocr_box_counts = []
        self.total_times = []
        self.total_frames = 0
        self.processed_frames = 0
        self.success_count = 0
        self.failure_count = 0
        self.cpu_samples = []
        self.mem_samples = []
        self.gpu_util_samples = []
        self.gpu_mem_samples = []
        self.start_time = time.time()
        self.last_fps = 0.0

    def start_run(self) -> None:
        """开始一次新的性能监控周期"""
        self.reset()
        os.makedirs(self.log_dir, exist_ok=True)
        self._run_started = True

    def start_timer(self) -> float:
        return time.perf_counter()

    def stop_timer(self, start_time: float) -> float:
        return (time.perf_counter() - start_time) * 1000.0

    def record_raw_frame(self) -> None:
        """记录原始帧（无论是否做OCR），用于统计总帧率"""
        self.total_frames += 1

    def record_metrics(self, ocr_ms: Optional[float], total_ms: Optional[float], success: bool = True, ocr_boxes: int = 1) -> None:
        if ocr_ms is not None:
            self.ocr_times.append(ocr_ms)
            # 记录对应的OCR框数量（至少为1，避免0导致除零问题）
            self.ocr_box_counts.append(max(int(ocr_boxes or 0), 1))
        if total_ms is not None:
            self.total_times.append(total_ms)
            if total_ms > 0:
                self.last_fps = 1000.0 / total_ms

        self.processed_frames += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        self.update_system_metrics()

    def update_system_metrics(self) -> None:
        if self._process:
            try:
                cpu_percent = self._process.cpu_percent(None)
                if cpu_percent is not None:
                    cpu_count = psutil.cpu_count() or 1
                    # 归一化到0-100%
                    self.cpu_samples.append(cpu_percent / max(cpu_count, 1))
            except Exception:
                pass

            try:
                mem_mb = self._process.memory_info().rss / (1024 * 1024)
                self.mem_samples.append(mem_mb)
            except Exception:
                pass

        if self.enable_gpu_monitor:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    self.gpu_util_samples.append(gpu.load * 100.0)
                    self.gpu_mem_samples.append(gpu.memoryUsed)
            except Exception:
                # GPU 监控失败时忽略，以免影响主流程
                pass

    @staticmethod
    def _avg(values) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def get_stats(self) -> dict:
        elapsed = max(time.time() - self.start_time, 1e-6)
        # 平均OCR处理时间（单次调用平均耗时）
        avg_ocr_ms = self._avg(self.ocr_times)
        # 单位框耗时：sum(ocr_ms) / sum(ocr_boxes)
        total_ocr_time = sum(self.ocr_times)
        total_ocr_boxes = sum(self.ocr_box_counts) if self.ocr_box_counts else 0
        unit_box_ms = (total_ocr_time / total_ocr_boxes) if total_ocr_boxes > 0 else 0.0
        avg_total_ms = self._avg(self.total_times)
        fps_runtime = self.processed_frames / elapsed
        avg_fps = fps_runtime if fps_runtime > 0 else 0.0
        return {
            # 保留原有平均OCR处理时间（ms），并新增单位框耗时（ms/框）
            "avg_ocr_ms": avg_ocr_ms,
            "unit_box_ms": unit_box_ms,
            "avg_total_ms": avg_total_ms,
            "avg_fps": avg_fps,
            "current_fps": self.last_fps,
            "avg_cpu": self._avg(self.cpu_samples),
            "avg_memory": self._avg(self.mem_samples),
            "avg_gpu_util": self._avg(self.gpu_util_samples),
            "avg_gpu_mem": self._avg(self.gpu_mem_samples),
            "total_frames": self.total_frames,
            "processed_frames": self.processed_frames,
            "success": self.success_count,
            "fail": self.failure_count,
            "success_rate": (self.success_count / max(self.success_count + self.failure_count, 1)) * 100.0,
            "runtime_seconds": elapsed,
            "runtime_str": self._format_seconds(elapsed),
        }

    def save_performance_log(self) -> str:
        """将当前监控数据写入 CSV 日志并返回文件路径"""
        if not self._run_started:
            return ""

        stats = self.get_stats()
        filename = f"{self.module_name}_performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output_path = os.path.join(self.log_dir, filename)

        rows = [
            ("指标", "数值", "单位"),
            ("单位框耗时", f"{stats['unit_box_ms']:.2f}", "ms/框"),
            ("平均OCR处理时间", f"{stats['avg_ocr_ms']:.2f}", "ms"),
            ("平均总处理时间", f"{stats['avg_total_ms']:.2f}", "ms"),
            ("平均FPS", f"{stats['avg_fps']:.2f}", "fps"),
            ("当前FPS", f"{stats['current_fps']:.2f}", "fps"),
            ("平均CPU使用率", f"{stats['avg_cpu']:.2f}", "%"),
            ("平均内存使用", f"{stats['avg_memory']:.2f}", "MB"),
            ("平均GPU使用率", f"{stats['avg_gpu_util']:.2f}", "%"),
            ("平均GPU显存", f"{stats['avg_gpu_mem']:.2f}", "MB"),
            ("总帧数", str(stats['total_frames']), "帧"),
            ("处理帧数", str(stats['processed_frames']), "帧"),
            ("OCR成功次数", str(stats['success']), "次"),
            ("OCR失败次数", str(stats['fail']), "次"),
            ("OCR成功率", f"{stats['success_rate']:.2f}", "%"),
            ("运行时间", f"{stats['runtime_seconds']:.2f}", "秒"),
            ("运行时间(格式化)", stats["runtime_str"], "-"),
        ]

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        # 一次运行仅生成一份日志，避免重复写入
        self._run_started = False

        return output_path

