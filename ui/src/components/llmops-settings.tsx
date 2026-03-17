'use client'

import {useCallback, useEffect, useRef, useState} from 'react'
import {toast} from 'sonner'
import {LayoutGrid, LayoutList, Loader2, Languages, Settings, Trash, Wrench} from 'lucide-react'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {Button} from '@/components/ui/button'
import {Separator} from '@/components/ui/separator'
import {Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet} from '@/components/ui/field'
import {Input} from '@/components/ui/input'
import {Item, ItemContent, ItemDescription, ItemGroup, ItemTitle} from '@/components/ui/item'
import {Badge} from '@/components/ui/badge'
import {Switch} from '@/components/ui/switch'
import {Textarea} from '@/components/ui/textarea'
import {configApi} from '@/lib/api'
import type {AgentConfig, LLMConfig, ListMCPServerItem, ListA2AServerItem} from '@/lib/api'

// ==================== 通用配置 ====================

type CommonSettingProps = {
  config: AgentConfig
  onChange: (config: AgentConfig) => void
}

function CommonSetting({config, onChange}: CommonSettingProps) {
  const handleChange = (field: keyof AgentConfig, value: string) => {
    const numValue = value === '' ? undefined : Number(value)
    onChange({...config, [field]: numValue})
  }

  return (
    <form className="w-full px-1" onSubmit={(e) => e.preventDefault()}>
      <FieldGroup>
        <FieldSet>
          <FieldLegend className="text-lg font-bold text-gray-700">通用配置</FieldLegend>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="max_iterations">最大计划迭代次数</FieldLabel>
              <Input
                id="max_iterations"
                type="number"
                placeholder="Agent最大迭代次数"
                value={config.max_iterations ?? 100}
                onChange={(e) => handleChange('max_iterations', e.target.value)}
                min={0}
                max={200}
              />
              <FieldDescription className="text-xs">
                执行Agent最大能迭代循环调用工具的次数，默认为100
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="max_retries">最大重试次数</FieldLabel>
              <Input
                id="max_retries"
                type="number"
                placeholder="LLM/Tool最大重试次数"
                value={config.max_retries ?? 3}
                onChange={(e) => handleChange('max_retries', e.target.value)}
                min={0}
                max={10}
              />
              <FieldDescription className="text-xs">
                默认情况下，最大重试次数为3
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="max_search_results">最大搜索结果</FieldLabel>
              <Input
                id="max_search_results"
                type="number"
                placeholder="搜索工具返回的最大结果数"
                value={config.max_search_results ?? 10}
                onChange={(e) => handleChange('max_search_results', e.target.value)}
                min={0}
                max={30}
              />
              <FieldDescription className="text-xs">
                默认情况下，每个搜索步骤包含 10 个结果。
              </FieldDescription>
            </Field>
          </FieldGroup>
        </FieldSet>
      </FieldGroup>
    </form>
  )
}

// ==================== 模型提供商 ====================

type LLMSettingProps = {
  config: LLMConfig
  onChange: (config: LLMConfig) => void
}

function LLMSetting({config, onChange}: LLMSettingProps) {
  const handleChange = (field: keyof LLMConfig, value: string) => {
    onChange({...config, [field]: value})
  }

  const handleNumberChange = (field: keyof LLMConfig, value: string) => {
    const numValue = value === '' ? undefined : Number(value)
    onChange({...config, [field]: numValue})
  }

  return (
    <form className="w-full px-1" onSubmit={(e) => e.preventDefault()}>
      <FieldGroup>
        <FieldSet>
          <FieldLegend className="text-lg font-bold text-gray-700">模型提供商</FieldLegend>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="base_url">提供商基础地址(base_url)</FieldLabel>
              <Input
                id="base_url"
                type="url"
                placeholder="请填写LLM基础URL地址"
                value={config.base_url ?? ''}
                onChange={(e) => handleChange('base_url', e.target.value)}
              />
              <FieldDescription className="text-xs">
                请填写模型提供商的基础 url 地址，需兼容 OpenAI 格式。
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="api_key">提供商密钥</FieldLabel>
              <Input
                id="api_key"
                type="password"
                placeholder="请填写提供商API密钥"
                value={config.api_key ?? ''}
                onChange={(e) => handleChange('api_key', e.target.value)}
              />
              <FieldDescription className="text-xs">
                请填写模型提供商密钥信息。
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="model_name">模型名</FieldLabel>
              <Input
                id="model_name"
                type="text"
                placeholder="请填写需要使用的模型名字"
                value={config.model_name ?? ''}
                onChange={(e) => handleChange('model_name', e.target.value)}
              />
              <FieldDescription className="text-xs">
                请填写 llmops 调用的模型名字，模型必须支持工具调用、图像识别等功能。
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="temperature">温度(temperature)</FieldLabel>
              <Input
                id="temperature"
                type="number"
                placeholder="请填写模型温度"
                value={config.temperature ?? 0.7}
                onChange={(e) => handleNumberChange('temperature', e.target.value)}
                min={0}
                max={2}
                step={0.1}
              />
              <FieldDescription className="text-xs">
                温度越低，模型输出越确定、越稳定；温度越高，输出越具创造性和随机性，默认为 0.7。
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="max_tokens">最大输出 Token 数(max_tokens)</FieldLabel>
              <Input
                id="max_tokens"
                type="number"
                placeholder="请填写模型最大输出Token数"
                value={config.max_tokens ?? 8192}
                onChange={(e) => handleNumberChange('max_tokens', e.target.value)}
                min={1}
                max={128000}
              />
              <FieldDescription className="text-xs">
                模型单次回复允许生成的最大 Token 数量，默认为 8192。
              </FieldDescription>
            </Field>
          </FieldGroup>
        </FieldSet>
      </FieldGroup>
    </form>
  )
}

// ==================== A2A Agent 配置 ====================

type A2ASettingProps = {
  servers: ListA2AServerItem[]
  loading: boolean
  onToggleEnabled: (id: string, enabled: boolean) => void
  onDelete: (id: string) => void
  onAdd: (baseUrl: string) => Promise<boolean>
}

function A2ASetting({servers, loading, onToggleEnabled, onDelete, onAdd}: A2ASettingProps) {
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [addUrl, setAddUrl] = useState('')
  const [adding, setAdding] = useState(false)

  const handleAdd = async () => {
    if (!addUrl.trim()) {
      toast.error('请输入远程 Agent 地址')
      return
    }
    setAdding(true)
    try {
      const success = await onAdd(addUrl.trim())
      if (success) {
        setAddUrl('')
        setAddDialogOpen(false)
      }
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="w-full px-1">
      <FieldGroup>
        <FieldSet>
          <FieldLegend className="w-full flex justify-between items-center text-lg font-bold text-gray-700">
            A2A Agent 配置
            <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
              <DialogTrigger asChild>
                <Button type="button" size="xs" className="cursor-pointer">添加远程Agent</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle className="text-gray-700">添加远程Agent</DialogTitle>
                  <DialogDescription className="text-gray-500">
                    llmops 使用标准的 A2A 协议来连接远程 Agent。
                    <br/>
                    请将您的配置粘贴到下方，然后点击"添加"即可添加 Agent。
                  </DialogDescription>
                </DialogHeader>
                <form
                  className="w-full"
                  onSubmit={(e) => {
                    e.preventDefault()
                    handleAdd()
                  }}
                >
                  <FieldGroup>
                    <FieldSet>
                      <Field>
                        <Input
                          id="a2a_base_url"
                          type="url"
                          placeholder="Example: https://www.manus.llmops.com/weather-agent"
                          value={addUrl}
                          onChange={(e) => setAddUrl(e.target.value)}
                          disabled={adding}
                        />
                      </Field>
                    </FieldSet>
                  </FieldGroup>
                </form>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline" className="cursor-pointer" disabled={adding}>取消</Button>
                  </DialogClose>
                  <Button className="cursor-pointer" onClick={handleAdd} disabled={adding}>
                    {adding && <Loader2 className="animate-spin"/>}
                    添加
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </FieldLegend>
          <FieldDescription className="text-sm">
            模型上下文协议 (MCP) 通过集成外部工具来增强 llmops 的性能，例如私有域搜索、网页浏览、订餐、PPT 生成等任务。
          </FieldDescription>

          {/* 加载态 */}
          {loading && (
            <div className="flex justify-center py-8">
              <Loader2 className="size-6 animate-spin text-muted-foreground"/>
            </div>
          )}

          {/* 空态 */}
          {!loading && servers.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              暂无 A2A Agent，请点击上方按钮添加
            </div>
          )}

          {/* 列表 */}
          {!loading && servers.length > 0 && (
            <ItemGroup className="gap-3">
              {servers.map((server) => (
                <Item key={server.id} variant="outline">
                  <ItemContent>
                    <ItemTitle className="w-full flex justify-between items-center text-md font-bold text-gray-700">
                      <div className="flex gap-2 items-center">
                        {server.name}
                        {!server.enabled && <Badge>禁用</Badge>}
                      </div>
                      <div className="flex items-center justify-center gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          className="cursor-pointer"
                          onClick={() => onDelete(server.id)}
                        >
                          <Trash/>
                        </Button>
                        <Switch
                          checked={server.enabled}
                          onCheckedChange={(checked) => onToggleEnabled(server.id, checked)}
                        />
                      </div>
                    </ItemTitle>
                    {server.description && (
                      <ItemDescription>{server.description}</ItemDescription>
                    )}
                    <ItemDescription className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <LayoutList size={12}/>
                      {server.input_modes?.map((mode) => (
                        <Badge key={`in-${mode}`} variant="secondary" className="text-gray-500">
                          输入: {mode}
                        </Badge>
                      ))}
                      {server.output_modes?.map((mode) => (
                        <Badge key={`out-${mode}`} variant="secondary" className="text-gray-500">
                          输出: {mode}
                        </Badge>
                      ))}
                      <Badge variant={server.streaming ? 'secondary' : 'outline'}
                             className={server.streaming ? 'text-gray-500' : 'text-gray-400'}>
                        流式输出: {server.streaming ? '开启' : '关闭'}
                      </Badge>
                      <Badge variant={server.push_notifications ? 'secondary' : 'outline'}
                             className={server.push_notifications ? 'text-gray-500' : 'text-gray-400'}>
                        推送通知: {server.push_notifications ? '开启' : '关闭'}
                      </Badge>
                    </ItemDescription>
                  </ItemContent>
                </Item>
              ))}
            </ItemGroup>
          )}
        </FieldSet>
      </FieldGroup>
    </div>
  )
}

// ==================== MCP 服务器 ====================

type MCPSettingProps = {
  servers: ListMCPServerItem[]
  loading: boolean
  onToggleEnabled: (serverName: string, enabled: boolean) => void
  onDelete: (serverName: string) => void
  onAdd: (config: string) => Promise<boolean>
}

function MCPSetting({servers, loading, onToggleEnabled, onDelete, onAdd}: MCPSettingProps) {
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [addConfig, setAddConfig] = useState('')
  const [adding, setAdding] = useState(false)

  const mcpConfigPlaceholder = `{
  "mcpServers": {
    "qiniu": {
      "command": "uvx",
      "args": [
        "qiniu-mcp-server"
      ],
      "env": {
        "QINIU_ACCESS_KEY": "YOUR_ACCESS_KEY",
        "QINIU_SECRET_KEY": "YOUR_SECRET_KEY"
      }
    }
  }
}`

  const handleAdd = async () => {
    if (!addConfig.trim()) {
      toast.error('请输入 MCP 服务器配置')
      return
    }
    setAdding(true)
    try {
      const success = await onAdd(addConfig.trim())
      if (success) {
        setAddConfig('')
        setAddDialogOpen(false)
      }
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="w-full px-1">
      <FieldGroup>
        <FieldSet>
          <FieldLegend className="w-full flex justify-between items-center text-lg font-bold text-gray-700">
            MCP 服务器
            <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
              <DialogTrigger asChild>
                <Button type="button" size="xs" className="cursor-pointer">添加服务器</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle className="text-gray-700">添加新的 MCP 服务器</DialogTitle>
                  <DialogDescription className="text-gray-500">
                    llmops 使用标准的 JSON MCP 配置来创建新服务器。
                    请将您的配置粘贴到下方，然后点击"添加"即可添加新服务器。
                  </DialogDescription>
                </DialogHeader>
                <form
                  className="w-full"
                  onSubmit={(e) => {
                    e.preventDefault()
                    handleAdd()
                  }}
                >
                  <FieldGroup>
                    <FieldSet>
                      <Field>
                        <Textarea
                          id="mcp_config"
                          placeholder={mcpConfigPlaceholder}
                          value={addConfig}
                          onChange={(e) => setAddConfig(e.target.value)}
                          className="min-h-[200px] font-mono text-xs"
                          disabled={adding}
                        />
                      </Field>
                    </FieldSet>
                  </FieldGroup>
                </form>
                <DialogFooter>
                  <DialogClose asChild>
                    <Button variant="outline" className="cursor-pointer" disabled={adding}>取消</Button>
                  </DialogClose>
                  <Button className="cursor-pointer" onClick={handleAdd} disabled={adding}>
                    {adding && <Loader2 className="animate-spin"/>}
                    添加
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </FieldLegend>
          <FieldDescription className="text-sm">
            模型上下文协议 (MCP) 通过集成外部工具来增强 llmops 的性能，例如私有域搜索、网页浏览、订餐、PPT 生成等任务。
          </FieldDescription>

          {/* 加载态 */}
          {loading && (
            <div className="flex justify-center py-8">
              <Loader2 className="size-6 animate-spin text-muted-foreground"/>
            </div>
          )}

          {/* 空态 */}
          {!loading && servers.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              暂无 MCP 服务器，请点击上方按钮添加
            </div>
          )}

          {/* 列表 */}
          {!loading && servers.length > 0 && (
            <ItemGroup className="gap-3">
              {servers.map((server) => (
                <Item key={server.server_name} variant="outline">
                  <ItemContent>
                    <ItemTitle className="w-full flex justify-between items-center text-md font-bold text-gray-700">
                      <div className="flex gap-2 items-center">
                        {server.server_name}
                        <Badge>{server.transport}</Badge>
                        {!server.enabled && <Badge>禁用</Badge>}
                      </div>
                      <div className="flex items-center justify-center gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          className="cursor-pointer"
                          onClick={() => onDelete(server.server_name)}
                        >
                          <Trash/>
                        </Button>
                        <Switch
                          checked={server.enabled}
                          onCheckedChange={(checked) => onToggleEnabled(server.server_name, checked)}
                        />
                      </div>
                    </ItemTitle>
                    {server.tools.length > 0 && (
                      <ItemDescription className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <Wrench size={12}/>
                        {server.tools.map((tool) => (
                          <Badge key={tool} variant="secondary" className="text-gray-500">
                            {tool}
                          </Badge>
                        ))}
                      </ItemDescription>
                    )}
                  </ItemContent>
                </Item>
              ))}
            </ItemGroup>
          )}
        </FieldSet>
      </FieldGroup>
    </div>
  )
}

// ==================== 设置弹窗主组件 ====================

type SettingTab = 'common-setting' | 'llm-setting' | 'a2a-setting' | 'mcp-setting'

const SETTING_MENUS: Array<{
  key: SettingTab
  icon: typeof Settings
  title: string
}> = [
  {key: 'common-setting', icon: Settings, title: '通用配置'},
  {key: 'llm-setting', icon: Languages, title: '模型提供商'},
  {key: 'a2a-setting', icon: LayoutGrid, title: 'A2A Agent 配置'},
  {key: 'mcp-setting', icon: Wrench, title: 'MCP 服务器'},
]

export function LlmopsSettings() {
  // ---- 防止 SSR hydration 不匹配（Radix Dialog 在服务端/客户端生成不同的 aria-controls ID）----
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  // ---- 弹窗 & 导航 ----
  const [open, setOpen] = useState(false)
  const [activeSetting, setActiveSetting] = useState<SettingTab>('common-setting')

  // ---- 数据 ----
  const [agentConfig, setAgentConfig] = useState<AgentConfig>({})
  const [llmConfig, setLlmConfig] = useState<LLMConfig>({})
  const [mcpServers, setMcpServers] = useState<ListMCPServerItem[]>([])
  const [a2aServers, setA2aServers] = useState<ListA2AServerItem[]>([])

  // ---- 状态 ----
  const [loadingConfig, setLoadingConfig] = useState(false)
  const [loadingMCP, setLoadingMCP] = useState(false)
  const [loadingA2A, setLoadingA2A] = useState(false)
  const [saving, setSaving] = useState(false)

  // 防止 Strict Mode 重复获取
  const fetchingRef = useRef(false)

  // ---- 数据拉取（各接口独立请求、独立更新，互不阻塞） ----
  const fetchAllConfigs = useCallback(() => {
    if (fetchingRef.current) return
    fetchingRef.current = true

    // 1. Agent + LLM 配置（通常很快）
    setLoadingConfig(true)
    Promise.all([
      configApi.getAgentConfig(),
      configApi.getLLMConfig(),
    ])
      .then(([agent, llm]) => {
        setAgentConfig(agent)
        setLlmConfig(llm)
      })
      .catch((err) => {
        console.error('[Settings] 获取基础配置失败:', err)
      })
      .finally(() => {
        setLoadingConfig(false)
      })

    // 2. MCP 服务器列表（可能较慢）
    setLoadingMCP(true)
    configApi
      .getMCPServers()
      .then((data) => {
        setMcpServers(data?.mcp_servers ?? [])
      })
      .catch((err) => {
        console.error('[Settings] 获取 MCP 服务器列表失败:', err)
      })
      .finally(() => {
        setLoadingMCP(false)
      })

    // 3. A2A 服务器列表
    setLoadingA2A(true)
    configApi
      .getA2AServers()
      .then((data) => {
        setA2aServers(data?.a2a_servers ?? [])
      })
      .catch((err) => {
        console.error('[Settings] 获取 A2A 服务器列表失败:', err)
      })
      .finally(() => {
        setLoadingA2A(false)
      })
  }, [])

  // 弹窗打开时拉取数据
  useEffect(() => {
    if (open) {
      fetchAllConfigs()
    } else {
      // 弹窗关闭时重置 ref，下次打开可以重新获取
      fetchingRef.current = false
    }
  }, [open, fetchAllConfigs])

  // ---- 保存 (通用配置 / LLM) ----
  const handleSave = async () => {
    setSaving(true)
    try {
      if (activeSetting === 'common-setting') {
        await configApi.updateAgentConfig(agentConfig)
        toast.success('通用配置保存成功')
      } else if (activeSetting === 'llm-setting') {
        await configApi.updateLLMConfig(llmConfig)
        toast.success('模型提供商配置保存成功')
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '保存失败'
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  // ---- MCP 操作 ----
  const handleMCPToggle = useCallback(async (serverName: string, enabled: boolean) => {
    // 乐观更新
    setMcpServers((prev) =>
      prev.map((s) => (s.server_name === serverName ? {...s, enabled} : s)),
    )
    try {
      await configApi.updateMCPServerEnabled(serverName, enabled)
      toast.success(`${serverName} 已${enabled ? '启用' : '禁用'}`)
    } catch {
      // 回滚
      setMcpServers((prev) =>
        prev.map((s) => (s.server_name === serverName ? {...s, enabled: !enabled} : s)),
      )
      toast.error(`操作失败，请重试`)
    }
  }, [])

  const handleMCPDelete = useCallback(async (serverName: string) => {
    const prev = mcpServers
    // 乐观更新
    setMcpServers((list) => list.filter((s) => s.server_name !== serverName))
    try {
      await configApi.deleteMCPServer(serverName)
      toast.success(`已删除 MCP 服务器「${serverName}」`)
    } catch {
      setMcpServers(prev)
      toast.error(`删除失败，请重试`)
    }
  }, [mcpServers])

  const handleMCPAdd = useCallback(async (configText: string): Promise<boolean> => {
    try {
      const parsed = JSON.parse(configText)
      await configApi.addMCPServer(parsed)
      toast.success('MCP 服务器添加成功')
      // 重新拉取列表
      try {
        const data = await configApi.getMCPServers()
        setMcpServers(data?.mcp_servers ?? [])
      } catch { /* 忽略刷新失败 */ }
      return true
    } catch (err) {
      if (err instanceof SyntaxError) {
        toast.error('JSON 格式错误，请检查配置')
      } else {
        toast.error(err instanceof Error ? err.message : '添加失败')
      }
      return false
    }
  }, [])

  // ---- A2A 操作 ----
  const handleA2AToggle = useCallback(async (id: string, enabled: boolean) => {
    setA2aServers((prev) =>
      prev.map((s) => (s.id === id ? {...s, enabled} : s)),
    )
    try {
      await configApi.updateA2AServerEnabled(id, enabled)
      const server = a2aServers.find((s) => s.id === id)
      toast.success(`${server?.name ?? 'Agent'} 已${enabled ? '启用' : '禁用'}`)
    } catch {
      setA2aServers((prev) =>
        prev.map((s) => (s.id === id ? {...s, enabled: !enabled} : s)),
      )
      toast.error(`操作失败，请重试`)
    }
  }, [a2aServers])

  const handleA2ADelete = useCallback(async (id: string) => {
    const prev = a2aServers
    const target = a2aServers.find((s) => s.id === id)
    setA2aServers((list) => list.filter((s) => s.id !== id))
    try {
      await configApi.deleteA2AServer(id)
      toast.success(`已删除 A2A Agent「${target?.name ?? id}」`)
    } catch {
      setA2aServers(prev)
      toast.error(`删除失败，请重试`)
    }
  }, [a2aServers])

  const handleA2AAdd = useCallback(async (baseUrl: string): Promise<boolean> => {
    try {
      await configApi.addA2AServer({base_url: baseUrl})
      toast.success('远程 Agent 添加成功')
      // 重新拉取列表
      try {
        const data = await configApi.getA2AServers()
        setA2aServers(data?.a2a_servers ?? [])
      } catch { /* 忽略刷新失败 */ }
      return true
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '添加失败')
      return false
    }
  }, [])

  // 客户端挂载前，仅渲染普通按钮占位，避免 Radix Dialog SSR hydration 不匹配
  if (!mounted) {
    return (
      <Button variant="outline" size="icon-sm" className="cursor-pointer">
        <Settings/>
      </Button>
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {/* 触发按钮 */}
      <DialogTrigger asChild>
        <Button variant="outline" size="icon-sm" className="cursor-pointer">
          <Settings/>
        </Button>
      </DialogTrigger>

      {/* 弹窗内容 */}
      <DialogContent className="!max-w-[850px]">
        {/* 头部 */}
        <DialogHeader className="border-b pb-4">
          <DialogTitle className="text-gray-700">llmops智能体设置</DialogTitle>
          <DialogDescription className="text-gray-500">在此管理您的智能体设置。</DialogDescription>
        </DialogHeader>

        {/* 中间主体 */}
        <div className="flex flex-row gap-4">
          {/* 左侧导航菜单 */}
          <div className="max-w-[180px]">
            <div className="flex flex-col gap-0">
              {SETTING_MENUS.map((menu) => (
                <Button
                  key={menu.key}
                  variant={activeSetting === menu.key ? 'default' : 'ghost'}
                  className="cursor-pointer justify-start"
                  onClick={() => setActiveSetting(menu.key)}
                >
                  <menu.icon/>
                  {menu.title}
                </Button>
              ))}
            </div>
          </div>

          {/* 分隔符 */}
          <Separator orientation="vertical"/>

          {/* 右侧内容 */}
          <div className="flex-1 h-[500px] scrollbar-hide overflow-y-auto">
            {loadingConfig && (activeSetting === 'common-setting' || activeSetting === 'llm-setting') ? (
              <div className="flex justify-center items-center h-full">
                <Loader2 className="size-6 animate-spin text-muted-foreground"/>
              </div>
            ) : (
              <>
                {activeSetting === 'common-setting' && (
                  <CommonSetting config={agentConfig} onChange={setAgentConfig}/>
                )}
                {activeSetting === 'llm-setting' && (
                  <LLMSetting config={llmConfig} onChange={setLlmConfig}/>
                )}
              </>
            )}
            {activeSetting === 'a2a-setting' && (
              <A2ASetting
                servers={a2aServers}
                loading={loadingA2A}
                onToggleEnabled={handleA2AToggle}
                onDelete={handleA2ADelete}
                onAdd={handleA2AAdd}
              />
            )}
            {activeSetting === 'mcp-setting' && (
              <MCPSetting
                servers={mcpServers}
                loading={loadingMCP}
                onToggleEnabled={handleMCPToggle}
                onDelete={handleMCPDelete}
                onAdd={handleMCPAdd}
              />
            )}
          </div>
        </div>

        {/* 底部按钮 */}
        <DialogFooter className="border-t pt-4">
          <DialogClose asChild>
            <Button variant="outline" className="cursor-pointer">取消</Button>
          </DialogClose>
          <Button
            className="cursor-pointer"
            disabled={saving}
            onClick={handleSave}
          >
            {saving && <Loader2 className="animate-spin"/>}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
