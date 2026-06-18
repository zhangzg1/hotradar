## 环境执行规范 (Environment Specifications)

* **环境隔离**：为确保系统环境纯净并规避依赖冲突，所有第三方库的安装及代码调试必须在虚拟环境 `ai-hotspot-monitor` 中执行。
* **状态校验**：在执行任何操作前，请务必核实当前的活动环境。若未处于目标环境，请使用 `conda` 命令进行切换：
  ```bash
  conda activate ai-hotspot-monitor
  ```
* **运行约束**：严禁在非隔离环境下进行开发或测试，以防止对宿主系统环境造成污染。
