"""Pure-Python Unity SerializedFile (.assets) parser — header + type table +
object table, with TypeTree-driven generic object reading. Targets version 22
(Unity 2023/6000). Zero deps.
"""
from __future__ import annotations
import struct


class Reader:
    def __init__(self, data, little=True):
        self.d = data; self.o = 0; self.little = little
        self.e = "<" if little else ">"

    def u8(self):  v = self.d[self.o]; self.o += 1; return v
    def i8(self):  v = struct.unpack_from("b", self.d, self.o)[0]; self.o += 1; return v
    def u16(self): v = struct.unpack_from(self.e + "H", self.d, self.o)[0]; self.o += 2; return v
    def i16(self): v = struct.unpack_from(self.e + "h", self.d, self.o)[0]; self.o += 2; return v
    def u32(self): v = struct.unpack_from(self.e + "I", self.d, self.o)[0]; self.o += 4; return v
    def i32(self): v = struct.unpack_from(self.e + "i", self.d, self.o)[0]; self.o += 4; return v
    def u64(self): v = struct.unpack_from(self.e + "Q", self.d, self.o)[0]; self.o += 8; return v
    def i64(self): v = struct.unpack_from(self.e + "q", self.d, self.o)[0]; self.o += 8; return v
    def f32(self): v = struct.unpack_from(self.e + "f", self.d, self.o)[0]; self.o += 4; return v
    def f64(self): v = struct.unpack_from(self.e + "d", self.d, self.o)[0]; self.o += 8; return v
    def cstr(self):
        e = self.d.index(0, self.o); s = self.d[self.o:e].decode("utf-8", "replace"); self.o = e + 1; return s
    def bytes(self, n): v = self.d[self.o:self.o + n]; self.o += n; return v
    def align(self):
        self.o = (self.o + 3) & ~3


class TypeNode:
    __slots__ = ("type", "name", "size", "index", "flags", "level", "meta", "children",
                 "version", "type_off", "name_off")
    def __init__(self):
        self.children = []


def _read_typetree_blob(r, version):
    # version >= 12 (and ==10): blob node format
    node_count = r.u32()
    string_buf_size = r.u32()
    nodes = []
    for _ in range(node_count):
        n = TypeNode()
        n.version = r.u16()
        n.level = r.u8()
        n.flags = r.u8() if version >= 19 else r.u8()  # typeFlags (1 byte)
        n.type_off = r.u32()  # name offset (into string buf, with high bit = builtin)
        n.name_off = r.u32()
        n.size = r.i32()
        n.index = r.u32()
        n.meta = r.u32()  # metaFlag
        if version >= 19:
            r.u64()  # ref type hash
        nodes.append(n)
    strbuf = r.bytes(string_buf_size)
    # common strings table is built-in; for offsets with high bit set, use a builtin table.
    def getstr(off):
        if off & 0x80000000:
            return _COMMON.get(off & 0x7fffffff, str(off & 0x7fffffff))
        e = strbuf.index(0, off)
        return strbuf[off:e].decode("utf-8", "replace")
    for n in nodes:
        n.type = getstr(n.type_off)
        n.name = getstr(n.name_off)
    return nodes


# Unity common string table (subset, offsets are well-known)
_COMMON = {
 0:"AABB",5:"AnimationClip",19:"AnimationCurve",34:"AnimationState",48:"Array",54:"Base",
 59:"BitField",68:"bitset",75:"bool",80:"char",85:"ColorRGBA",95:"Component",105:"data",
 110:"deque",116:"double",123:"dynamic_array",137:"FastPropertyName",154:"first",160:"float",
 166:"Font",171:"GameObject",182:"Generic Mono",195:"GradientNEW",207:"GUID",212:"GUIStyle",
 221:"int",225:"list",230:"long long",240:"map",244:"Matrix4x4f",256:"MdFour",263:"MonoBehaviour",
 277:"MonoScript",288:"m_ByteSize",299:"m_Curve",307:"m_EditorClassIdentifier",331:"m_EditorHideFlags",
 349:"m_Enabled",359:"m_ExtensionPtr",374:"m_GameObject",387:"m_Index",397:"m_IsArray",
 408:"m_IsStatic",419:"m_MetaFlag",430:"m_Name",439:"m_ObjectHideFlags",457:"m_PrefabInternal",
 474:"m_PrefabParentObject",495:"m_Script",505:"m_StaticEditorFlags",525:"m_Type",534:"m_Version",
 545:"Object",552:"pair",557:"PPtr<Component>",573:"PPtr<GameObject>",590:"PPtr<Material>",
 607:"PPtr<MonoBehaviour>",626:"PPtr<MonoScript>",643:"PPtr<Object>",657:"PPtr<Prefab>",
 671:"PPtr<Sprite>",684:"PPtr<TextAsset>",701:"PPtr<Texture>",716:"PPtr<Texture2D>",
 733:"PPtr<Transform>",750:"Prefab",757:"Quaternionf",769:"Rectf",775:"RectInt",784:"RectOffset",
 795:"second",802:"set",806:"short",812:"size",817:"SInt16",824:"SInt32",831:"SInt64",838:"SInt8",
 844:"staticvector",857:"string",864:"TextAsset",874:"TextMesh",883:"Texture",891:"Texture2D",
 901:"Transform",911:"TypelessData",924:"UInt16",931:"UInt32",938:"UInt64",945:"UInt8",951:"unsigned int",
 964:"unsigned long long",983:"unsigned short",997:"vector",1004:"Vector2f",1013:"Vector3f",
 1022:"Vector4f",1031:"m_ScriptingClassIdentifier",1058:"Gradient",1067:"Type*",1073:"int2_storage",
 1086:"int3_storage",1099:"BoundsInt",1109:"m_CorrespondingSourceObject",1136:"m_PrefabInstance",
 1152:"m_PrefabAsset",1166:"FileSize",1175:"Hash128",
}


def parse(data):
    r = Reader(data, little=False)
    metadata_size = r.u32(); file_size = r.u32(); version = r.u32(); data_offset = r.u32()
    endianness = 0
    if version >= 9:
        endianness = r.u8(); r.bytes(3)
    if version >= 22:
        metadata_size = r.u32(); file_size = r.i64(); data_offset = r.i64(); r.i64()
    little = (endianness == 0)
    r.little = little; r.e = "<" if little else ">"

    unity_ver = r.cstr()
    target_platform = r.u32()
    enable_typetree = bool(r.u8()) if version >= 13 else True

    type_count = r.u32()
    types = []
    for _ in range(type_count):
        class_id = r.i32()
        stripped = r.u8() if version >= 16 else 0
        script_type_index = r.i16() if version >= 17 else -1
        if version >= 13:
            if (version < 16 and class_id < 0) or (version >= 16 and class_id == 114):
                r.bytes(16)  # script id hash
            r.bytes(16)      # old type hash
        tt = _read_typetree_blob(r, version) if enable_typetree else None
        if enable_typetree and version >= 21:
            dep_count = r.u32(); r.bytes(dep_count * 4)
        types.append((class_id, tt))

    obj_count = r.u32()
    objects = []
    for _ in range(obj_count):
        r.align()
        path_id = r.i64()
        if version >= 22:
            byte_start = r.i64()
        else:
            byte_start = r.u32()
        byte_size = r.u32()
        type_id = r.i32()
        objects.append((path_id, data_offset + byte_start, byte_size, type_id))
    return {"version": version, "little": little, "enable_typetree": enable_typetree,
            "types": types, "objects": objects, "data_offset": data_offset, "raw": data}


if __name__ == "__main__":
    import sys, collections
    from unityfs import read_bundle
    for nd, sf in read_bundle(sys.argv[1]):
        if not nd.path.endswith(".assets") and nd.path not in ("globalgamemanagers",):
            continue
        try:
            m = parse(sf)
        except Exception as ex:
            print(f"{nd.path}: parse error {ex}"); continue
        dist = collections.Counter(m["types"][t[3]][0] for t in m["objects"])
        print(f"{nd.path}: v{m['version']} typetree={m['enable_typetree']} "
              f"objs={len(m['objects'])} sprites(213)={dist.get(213,0)} "
              f"transforms(4)={dist.get(4,0)} GO(1)={dist.get(1,0)} MB(114)={dist.get(114,0)}")
