import sys
from typing import Dict
from unittest import TestCase, mock

# Ensure the module under test can be imported without optional dependencies installed.
if "pyodbc" not in sys.modules:
    sys.modules["pyodbc"] = mock.MagicMock()
if "requests" not in sys.modules:
    sys.modules["requests"] = mock.MagicMock()

from winthor_automation.src import winthor_address_updater as updater


class NormalizeAddressTests(TestCase):
    def test_normalize_address_uppercases_and_strips(self) -> None:
        payload: Dict[str, str] = {
            "logradouro": "  Rua das Flores  ",
            "numero": " 123 ",
            "complemento": " apto 45 ",
            "bairro": " centro ",
            "municipio": " São Paulo ",
            "uf": " sp ",
            "cep": " 01001-000 ",
        }

        address = updater.normalize_address(payload)

        self.assertEqual(address.street, "RUA DAS FLORES")
        self.assertEqual(address.number, "123")
        self.assertEqual(address.complement, "APTO 45")
        self.assertEqual(address.district, "CENTRO")
        self.assertEqual(address.city, "SÃO PAULO")
        self.assertEqual(address.state, "SP")
        self.assertEqual(address.zipcode, "01001-000")


class NeedsUpdateTests(TestCase):
    def test_needs_update_detects_identical_address(self) -> None:
        current = {
            "endereco": "Rua das Flores",
            "numero": "123",
            "complemento": "Apto 45",
            "bairro": "Centro",
            "cidade": "São Paulo",
            "uf": "SP",
            "cep": "01001-000",
        }
        new_address = updater.Address(
            street="RUA DAS FLORES",
            number="123",
            complement="APTO 45",
            district="CENTRO",
            city="SÃO PAULO",
            state="SP",
            zipcode="01001-000",
        )

        self.assertFalse(updater.needs_update(current, new_address))

    def test_needs_update_detects_difference(self) -> None:
        current = {
            "endereco": "Rua antiga",
            "numero": "321",
            "complemento": "",
            "bairro": "Bairro",
            "cidade": "Cidade",
            "uf": "SP",
            "cep": "99999-999",
        }
        new_address = updater.Address(
            street="RUA NOVA",
            number="123",
            complement="APTO 1",
            district="CENTRO",
            city="SÃO PAULO",
            state="SP",
            zipcode="01001-000",
        )

        self.assertTrue(updater.needs_update(current, new_address))


class RunBatchTests(TestCase):
    def setUp(self) -> None:
        self.logger = mock.MagicMock()

    def _build_client(self) -> updater.ClientRecord:
        return updater.ClientRecord(
            client_id=1,
            cnpj="12.345.678/0001-90",
            razao_social="Empresa Teste",
            endereco={
                "endereco": "RUA ANTIGA",
                "numero": "321",
                "complemento": "",
                "bairro": "BAIRRO",
                "cidade": "CIDADE",
                "uf": "SP",
                "cep": "99999-999",
            },
        )

    def test_run_batch_updates_when_address_differs(self) -> None:
        client = self._build_client()
        mock_db = mock.MagicMock()
        mock_db.fetch_clients_pending_validation.return_value = [client]
        mock_db.update_client_address = mock.MagicMock()
        mock_db.record_failure = mock.MagicMock()

        mock_api = mock.MagicMock()
        mock_api.fetch_company_data.return_value = {
            "logradouro": "Rua Nova",
            "numero": "123",
            "complemento": "APTO 1",
            "bairro": "Centro",
            "municipio": "São Paulo",
            "uf": "SP",
            "cep": "01001-000",
        }

        processed, updated, failures = updater.run_batch(
            mock_db, mock_api, batch_size=10, logger=self.logger
        )

        self.assertEqual(processed, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(failures, [])
        mock_db.update_client_address.assert_called_once()
        mock_db.record_failure.assert_not_called()

    def test_run_batch_records_failure_on_incomplete_address(self) -> None:
        client = self._build_client()
        mock_db = mock.MagicMock()
        mock_db.fetch_clients_pending_validation.return_value = [client]
        mock_db.update_client_address = mock.MagicMock()
        mock_db.record_failure = mock.MagicMock()

        mock_api = mock.MagicMock()
        mock_api.fetch_company_data.return_value = {
            "logradouro": "",
            "municipio": "",
            "uf": "",
        }

        processed, updated, failures = updater.run_batch(
            mock_db, mock_api, batch_size=10, logger=self.logger
        )

        self.assertEqual(processed, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(len(failures), 1)
        failure_client_id, reason = failures[0]
        self.assertEqual(failure_client_id, client.client_id)
        self.assertIn("Incomplete address", reason)
        mock_db.update_client_address.assert_not_called()
        mock_db.record_failure.assert_called_once()
