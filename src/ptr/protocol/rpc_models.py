"""Modelos para mensajes JSON-RPC 2.0 y constantes de error del protocolo."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

# Códigos de error estándar JSON-RPC y del protocolo ptr (§10.5)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

AUTH_FAILED = -32001
NO_PROJECT = -32002
PDF_UNSUPPORTED = -32003
ENGINE_NOT_LOADED = -32004
ENGINE_FAILED = -32005
REVISION_CONFLICT = -32006
JOB_NOT_FOUND = -32007
JOB_BUSY = -32008
EXPORT_FAILED = -32009
PROTOCOL_MISMATCH = -32010
OUT_OF_MEMORY = -32011


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[Union[int, str]] = None
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class JsonRpcErrorData(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[Union[int, str]] = None
    result: Optional[Any] = None
    error: Optional[JsonRpcErrorData] = None


class JsonRpcNotification(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)
