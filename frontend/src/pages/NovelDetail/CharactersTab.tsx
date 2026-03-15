import { useEffect, useState, useCallback } from 'react';
import {
  Row, Col, Spin, Empty, Drawer, Descriptions, Typography, Button, Space, Modal, Form, Input, Select, InputNumber, message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, RocketOutlined } from '@ant-design/icons';
import type { Character } from '@/api/types';
import { getCharacters, createCharacter, updateCharacter, deleteCharacter } from '@/api/characters';
import CharacterCard from '@/components/CharacterCard';
import { ROLE_TYPE_MAP, GENDER_MAP } from '@/utils/constants';
import RelationshipGraph from './RelationshipGraph';

interface Props {
  novelId: string;
}

const roleOptions = Object.entries(ROLE_TYPE_MAP).map(([value, { label }]) => ({ value, label }));
const genderOptions = Object.entries(GENDER_MAP).map(([value, label]) => ({ value, label }));

export default function CharactersTab({ novelId }: Props) {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Character | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const fetchCharacters = useCallback(async (nid: string) => {
    setLoading(true);
    try {
      const data = await getCharacters(nid);
      setCharacters(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCharacters(novelId);
  }, [novelId, fetchCharacters]);

  const handleCreate = async () => {
    setCreateLoading(true);
    try {
      const values = await createForm.validateFields();
      await createCharacter(novelId, values);
      message.success('角色创建成功');
      setCreateOpen(false);
      createForm.resetFields();
      void fetchCharacters(novelId);
    } finally {
      setCreateLoading(false);
    }
  };

  const handleOpenEdit = () => {
    if (!selected) return;
    editForm.setFieldsValue({
      name: selected.name,
      role_type: selected.role_type,
      gender: selected.gender,
      age: selected.age,
      appearance: selected.appearance || '',
      personality: selected.personality || '',
      background: selected.background || '',
      goals: selected.goals || '',
    });
    setEditMode(true);
  };

  const handleSaveEdit = async () => {
    if (!selected) return;
    setEditLoading(true);
    try {
      const values = await editForm.validateFields();
      await updateCharacter(novelId, selected.id, values);
      message.success('角色已更新');
      setEditMode(false);
      setSelected(null);
      void fetchCharacters(novelId);
    } finally {
      setEditLoading(false);
    }
  };

  const handleDelete = () => {
    if (!selected) return;
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除角色「${selected.name}」吗？此操作不可撤销。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        await deleteCharacter(novelId, selected.id);
        message.success('角色已删除');
        setSelected(null);
        setEditMode(false);
        void fetchCharacters(novelId);
      },
    });
  };

  const handleDrawerClose = () => {
    setSelected(null);
    setEditMode(false);
  };

  if (loading) return <Spin />;
  if (characters.length === 0 && !createOpen) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div>
            <Typography.Title level={5} style={{ marginBottom: 8 }}>角色尚未生成</Typography.Title>
            <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
              点击下方按钮前往「概览」标签页启动企划，或手动添加角色
            </Typography.Text>
            <Space>
              <Button type="primary" icon={<RocketOutlined />} onClick={() => {
                const overviewTab = document.querySelector('[data-node-key="overview"]') as HTMLElement;
                overviewTab?.click();
              }}>
                前往开始企划
              </Button>
              <Button icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
                手动添加角色
              </Button>
            </Space>
          </div>
        }
      >
        <CreateModal
          open={createOpen}
          loading={createLoading}
          form={createForm}
          onOk={handleCreate}
          onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
        />
      </Empty>
    );
  }

  return (
    <div>
      <Row gutter={16}>
        <Col xs={24} md={10}>
          <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <Typography.Title level={5} style={{ margin: 0 }}>角色列表 ({characters.length})</Typography.Title>
            <Button size="small" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>添加角色</Button>
          </Space>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {characters.map((c) => (
              <CharacterCard key={c.id} character={c} onClick={() => { setSelected(c); setEditMode(false); }} />
            ))}
          </div>
        </Col>
        <Col xs={24} md={14}>
          <Typography.Title level={5}>关系图谱</Typography.Title>
          <div style={{ height: 500, border: '1px solid #f0f0f0', borderRadius: 8 }}>
            <RelationshipGraph novelId={novelId} />
          </div>
        </Col>
      </Row>

      <Drawer
        title={editMode ? '编辑角色' : (selected?.name || '角色详情')}
        open={!!selected}
        onClose={handleDrawerClose}
        size={480}
        extra={
          !editMode ? (
            <Space>
              <Button size="small" icon={<EditOutlined />} onClick={handleOpenEdit}>编辑</Button>
              <Button size="small" danger icon={<DeleteOutlined />} onClick={handleDelete}>删除</Button>
            </Space>
          ) : undefined
        }
      >
        {selected && !editMode && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="角色类型">
              {ROLE_TYPE_MAP[selected.role_type || 'minor']?.label}
            </Descriptions.Item>
            <Descriptions.Item label="性别">
              {selected.gender ? GENDER_MAP[selected.gender] || selected.gender : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="年龄">{selected.age ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="外貌">{selected.appearance || '-'}</Descriptions.Item>
            <Descriptions.Item label="性格">{selected.personality || '-'}</Descriptions.Item>
            <Descriptions.Item label="背景">{selected.background || '-'}</Descriptions.Item>
            <Descriptions.Item label="目标">{selected.goals || '-'}</Descriptions.Item>
            {selected.abilities && (
              <Descriptions.Item label="能力">
                <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(selected.abilities, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            {selected.growth_arc && (
              <Descriptions.Item label="成长轨迹">
                <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(selected.growth_arc, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
        {selected && editMode && (
          <Form form={editForm} layout="vertical">
            <CharacterFormFields />
            <Space style={{ marginTop: 16 }}>
              <Button type="primary" onClick={handleSaveEdit} loading={editLoading}>保存</Button>
              <Button onClick={() => setEditMode(false)}>取消</Button>
            </Space>
          </Form>
        )}
      </Drawer>

      <CreateModal
        open={createOpen}
        loading={createLoading}
        form={createForm}
        onOk={handleCreate}
        onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
      />
    </div>
  );
}

function CharacterFormFields() {
  return (
    <>
      <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入角色名称' }]}>
        <Input placeholder="角色名称" />
      </Form.Item>
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="role_type" label="类型">
            <Select options={roleOptions} allowClear placeholder="选择类型" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="gender" label="性别">
            <Select options={genderOptions} allowClear placeholder="选择性别" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="age" label="年龄">
            <InputNumber min={0} style={{ width: '100%' }} placeholder="年龄" />
          </Form.Item>
        </Col>
      </Row>
      <Form.Item name="appearance" label="外貌">
        <Input.TextArea rows={2} placeholder="外貌描述" />
      </Form.Item>
      <Form.Item name="personality" label="性格">
        <Input.TextArea rows={2} placeholder="性格描述" />
      </Form.Item>
      <Form.Item name="background" label="背景">
        <Input.TextArea rows={2} placeholder="背景故事" />
      </Form.Item>
      <Form.Item name="goals" label="目标">
        <Input.TextArea rows={2} placeholder="目标动机" />
      </Form.Item>
    </>
  );
}

function CreateModal({ open, loading, form, onOk, onCancel }: {
  open: boolean;
  loading: boolean;
  form: ReturnType<typeof Form.useForm>[0];
  onOk: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      title="添加角色"
      open={open}
      onOk={onOk}
      confirmLoading={loading}
      onCancel={onCancel}
      okText="创建"
      width={560}
    >
      <Form form={form} layout="vertical">
        <CharacterFormFields />
      </Form>
    </Modal>
  );
}
