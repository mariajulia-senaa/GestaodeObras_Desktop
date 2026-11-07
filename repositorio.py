"""Persistência em SQLite (Nível 3).

O repositório carrega e grava o agregado completo: uma Obra com suas Etapas e
os Recursos de cada Etapa. As regras de negócio continuam no domínio.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from dominio import (
    Engenheiro, Equipamento, Etapa, ErroValidacao, Material, Obra, Recurso,
    StatusEtapa, StatusObra,
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS obra (
    id      INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL,
    status  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS etapa (
    obra_id           INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
    id                INTEGER NOT NULL,
    nome              TEXT NOT NULL,
    status            TEXT NOT NULL,
    percentual        REAL NOT NULL DEFAULT 0,
    inicio_planejado  TEXT,
    fim_planejado     TEXT,
    custo_planejado   REAL,
    inicio_real       TEXT,
    fim_real          TEXT,
    custo_real        REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (obra_id, id)
);

CREATE TABLE IF NOT EXISTS recurso (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id          INTEGER NOT NULL,
    etapa_id         INTEGER NOT NULL,
    tipo             TEXT NOT NULL CHECK (tipo IN ('MATERIAL', 'EQUIPAMENTO')),
    nome             TEXT NOT NULL,
    quantidade_horas REAL NOT NULL,
    valor_unitario   REAL NOT NULL,
    FOREIGN KEY (obra_id, etapa_id) REFERENCES etapa(obra_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS usuario (
    nome        TEXT PRIMARY KEY,
    salt        BLOB NOT NULL,
    senha_hash  BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS alocacao (
    usuario_nome  TEXT    NOT NULL REFERENCES usuario(nome) ON DELETE CASCADE,
    obra_id       INTEGER NOT NULL REFERENCES obra(id) ON DELETE CASCADE,
    PRIMARY KEY (usuario_nome, obra_id)
);
"""


def _data_para_texto(valor: Optional[date]) -> Optional[str]:
    return valor.isoformat() if valor else None


def _texto_para_data(texto: Optional[str]) -> Optional[date]:
    return date.fromisoformat(texto) if texto else None


class RepositorioSQLite:
    def __init__(self, caminho: str = ":memory:"):
        self._con = sqlite3.connect(caminho)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.executescript(ESQUEMA)
        self._con.commit()

    def fechar(self) -> None:
        self._con.close()

    # ---------- Obras ----------

    def cadastrar(self, obra: Obra) -> Obra:
        if self.contem_id(obra.id):
            raise ErroValidacao("Já existe uma obra com este Código (ID).")
        self.salvar(obra)
        return obra

    def salvar(self, obra: Obra) -> None:
        """Grava a obra inteira (obra, etapas e recursos) em uma única transação."""
        with self._con:
            self._con.execute(
                "INSERT INTO obra (id, nome, status) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, status = excluded.status",
                (obra.id, obra.nome, obra.status.value),
            )
            self._con.execute("DELETE FROM etapa WHERE obra_id = ?", (obra.id,))  # recursos saem em cascata
            for e in obra.etapas:
                self._con.execute(
                    "INSERT INTO etapa (obra_id, id, nome, status, percentual, inicio_planejado, "
                    "fim_planejado, custo_planejado, inicio_real, fim_real, custo_real) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (obra.id, e.id, e.nome, e.status.value, e.percentual_conclusao,
                     _data_para_texto(e.data_inicio_planejada), _data_para_texto(e.data_fim_planejada),
                     e.custo_planejado, _data_para_texto(e.data_inicio_real),
                     _data_para_texto(e.data_fim_real), e.custo_real),
                )
                for r in e.recursos:
                    tipo, qtd_horas, valor = self._decompor_recurso(r)
                    self._con.execute(
                        "INSERT INTO recurso (obra_id, etapa_id, tipo, nome, quantidade_horas, valor_unitario) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (obra.id, e.id, tipo, r.nome, qtd_horas, valor),
                    )

    def buscar_por_id(self, id_obra: int) -> Optional[Obra]:
        linha = self._con.execute("SELECT * FROM obra WHERE id = ?", (id_obra,)).fetchone()
        return self._montar_obra(linha) if linha else None

    def listar_todas(self) -> list[Obra]:
        linhas = self._con.execute("SELECT * FROM obra ORDER BY id").fetchall()
        return [self._montar_obra(l) for l in linhas]

    def listar_ativas(self) -> list[Obra]:
        return [o for o in self.listar_todas() if o.esta_em_andamento()]

    def contem_id(self, id_obra: int) -> bool:
        return self._con.execute("SELECT 1 FROM obra WHERE id = ?", (id_obra,)).fetchone() is not None

    def contem(self, obra: Obra) -> bool:
        return self.contem_id(obra.id)

    # ---------- Engenheiros ----------

    def cadastrar_engenheiro(self, engenheiro: Engenheiro) -> Engenheiro:
        if self.buscar_engenheiro(engenheiro.nome) is not None:
            raise ErroValidacao("Já existe um usuário com este nome.")
        with self._con:
            self._con.execute(
                "INSERT INTO usuario (nome, salt, senha_hash) VALUES (?, ?, ?)",
                (engenheiro.nome, engenheiro.salt, engenheiro.senha_hash),
            )
        return engenheiro

    def buscar_engenheiro(self, nome: str) -> Optional[Engenheiro]:
        linha = self._con.execute("SELECT * FROM usuario WHERE nome = ?", (nome,)).fetchone()
        if linha is None:
            return None
        eng = Engenheiro(linha["nome"], salt=bytes(linha["salt"]), senha_hash=bytes(linha["senha_hash"]))
        ids = self._con.execute(
            "SELECT obra_id FROM alocacao WHERE usuario_nome = ? ORDER BY obra_id", (nome,)
        ).fetchall()
        for l in ids:
            obra = self.buscar_por_id(l["obra_id"])
            if obra is not None:
                eng.alocar_obra(obra)
        return eng

    def salvar_alocacoes(self, engenheiro: Engenheiro) -> None:
        with self._con:
            self._con.execute("DELETE FROM alocacao WHERE usuario_nome = ?", (engenheiro.nome,))
            self._con.executemany(
                "INSERT INTO alocacao (usuario_nome, obra_id) VALUES (?, ?)",
                [(engenheiro.nome, o.id) for o in engenheiro.obras_alocadas],
            )

    # ---------- Mapeamento interno ----------

    @staticmethod
    def _decompor_recurso(recurso: Recurso) -> tuple[str, float, float]:
        if isinstance(recurso, Material):
            return "MATERIAL", recurso.quantidade, recurso.preco_unitario
        if isinstance(recurso, Equipamento):
            return "EQUIPAMENTO", recurso.horas_uso, recurso.taxa_por_hora
        raise ErroValidacao(f"Tipo de recurso não suportado: {type(recurso).__name__}")

    @staticmethod
    def _montar_recurso(linha: sqlite3.Row) -> Recurso:
        fabricas = {"MATERIAL": Material, "EQUIPAMENTO": Equipamento}
        return fabricas[linha["tipo"]](linha["nome"], linha["quantidade_horas"], linha["valor_unitario"])

    def _montar_obra(self, linha: sqlite3.Row) -> Obra:
        obra = Obra(linha["id"], linha["nome"], StatusObra(linha["status"]))
        etapas = self._con.execute(
            "SELECT * FROM etapa WHERE obra_id = ? ORDER BY id", (obra.id,)
        ).fetchall()
        for le in etapas:
            etapa = Etapa(le["id"], le["nome"])
            etapa.status = StatusEtapa(le["status"])
            etapa.percentual_conclusao = le["percentual"]
            etapa.data_inicio_planejada = _texto_para_data(le["inicio_planejado"])
            etapa.data_fim_planejada = _texto_para_data(le["fim_planejado"])
            etapa.custo_planejado = le["custo_planejado"]
            etapa.data_inicio_real = _texto_para_data(le["inicio_real"])
            etapa.data_fim_real = _texto_para_data(le["fim_real"])
            etapa.custo_real = le["custo_real"]
            recursos = self._con.execute(
                "SELECT * FROM recurso WHERE obra_id = ? AND etapa_id = ? ORDER BY id",
                (obra.id, etapa.id),
            ).fetchall()
            for lr in recursos:
                etapa.adicionar_recurso(self._montar_recurso(lr))
            obra.restaurar_etapa(etapa)
        return obra
