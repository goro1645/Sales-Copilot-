# Sales Copilot stdio MCP Server Design

## Goal

把现有 `Sales Copilot` 的本地 `MCP 风格工具层` 升级为一个真正可通过 `stdio` 被外部客户端消费的 MCP server，同时保留当前 workflow 内部的 `direct/mcp` 模式不回归。

## Current State

当前项目已经具备：

- 本地工具服务实现：[D:\minimind\.worktrees\minimind-job-agent\sales_copilot\mcp_server.py](D:\minimind\.worktrees\minimind-job-agent\sales_copilot\mcp_server.py)
- 本地客户端封装：[D:\minimind\.worktrees\minimind-job-agent\sales_copilot\mcp_client.py](D:\minimind\.worktrees\minimind-job-agent\sales_copilot\mcp_client.py)
- workflow 对 `mcp` 模式的消费：[D:\minimind\.worktrees\minimind-job-agent\sales_copilot\graph.py](D:\minimind\.worktrees\minimind-job-agent\sales_copilot\graph.py)

当前缺失：

- 标准化 `tool discovery`
- 明确的参数 schema
- 真正的 `stdio` 传输层
- 外部客户端对 server 的真实消费验证

## Scope

本次只把 `CRM + Tasks` 工具层做硬，不扩到 retrieval 或 memory。

标准化的工具集合固定为：

1. `get_account`
2. `list_account_tasks`
3. `create_task`
4. `update_account_stage`

## Approach

### Option A: 自写轻量 stdio JSON-RPC

优点：

- 依赖少
- 控制力强

缺点：

- 更容易做成“像 MCP 但不够标准”
- 维护协议细节成本更高

### Option B: 使用 Python MCP SDK 构建 stdio server

优点：

- 更接近真实 MCP 实现
- 自带标准 server 抽象
- 更适合简历和面试表述

缺点：

- 需要安装 `mcp` 包
- 需要适配 SDK API

### Recommendation

优先采用 **Option B**。如果环境中 SDK 不可用或接口与当前项目不兼容，再回退到轻量自写版。但当前设计和计划都按 SDK 方案展开。

## Architecture

分成 4 层：

1. **Business tool layer**
   - 继续复用现有 `SalesCopilotMCPServer`
   - 保留工具业务逻辑，不把 SQLite 细节散落到协议层

2. **Schema layer**
   - 新增一个独立 schema 模块
   - 描述每个工具的名称、说明、参数 schema、返回语义

3. **stdio MCP server layer**
   - 新增 `mcp_stdio_server.py`
   - 负责启动 server、注册工具、暴露 `tool discovery` 与 `tool invocation`
   - 将 SDK 调用转发到业务工具层

4. **Verification layer**
   - 新增真实 `stdio` 集成测试或 smoke 测试
   - 验证外部客户端可以获取工具列表并调用工具

## File Plan

### Create

- `sales_copilot/mcp_schemas.py`
- `sales_copilot/mcp_stdio_server.py`
- `scripts/run_sales_copilot_mcp_server.py`
- `tests/sales_copilot/test_mcp_stdio_server.py`

### Modify

- `sales_copilot/mcp_server.py`
- `sales_copilot/mcp_client.py`
- `README.md`
- `requirements.txt` 或对应依赖说明文件（如果需要记录 `mcp`）

## Interfaces

### Tool Discovery

Server 必须能让外部客户端看到：

- 工具名
- 工具描述
- 参数 schema

### Tool Invocation

每个工具都必须：

- 校验参数
- 返回结构化对象
- 在非法参数和非法工具名时给出可理解错误

## Workflow Compatibility

现有 workflow 不强制改成通过 `stdio` 自己连自己。

兼容策略：

- 当前 `mcp_client.py` 继续保留为进程内 client
- `graph.py` 里的 `execution_mode="mcp"` 继续走本地 client
- 新增的 `stdio MCP server` 作为“外部可消费版本”

这样可以保证：

- 不破坏现有 demo 和评测
- 同时拿到更硬的 MCP 资产

## Testing

测试分三层：

1. **Schema / discovery tests**
   - 工具列表完整
   - 参数 schema 可见

2. **stdio server tests**
   - 外部客户端通过 stdio 能调用至少 `get_account`、`create_task`

3. **Regression tests**
   - 现有 `mcp_server.py`、`mcp_client.py`、workflow 相关测试继续通过

## Success Criteria

完成后满足以下条件：

1. 项目中存在真正的 `stdio MCP server` 入口
2. 工具具有明确 schema 和 discovery 能力
3. 至少一个外部客户端/验证脚本可真实消费该 server
4. 当前 `Sales Copilot` workflow 与离线评测链路不回归
5. README 中能清楚说明如何启动和验证 MCP server

## Resume / Interview Positioning

完成后可以更稳地写：

- 基于 `stdio` 实现 MCP server，提供标准化 `tool discovery / schema / invocation`
- 将本地 CRM/Tasks 工具以 MCP server 形式暴露，可被外部客户端或 Agent 消费

不再只是：

- “MCP 风格工具层”

