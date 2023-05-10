import datetime
import os.path
import re
from os.path import join

import pytest
import test_utils

from datashuttle.configs.canonical_tags import tags
from datashuttle.utils import formatting


class TestMakeFolders:
    """"""

    @pytest.fixture(scope="function")
    def project(test, tmp_path):
        """
        Create a project with default configs loaded.
        This makes a fresh project for each function,
        saved in the appdir path for platform independent
        and to avoid path setup on new machine.

        Ensure change folder at end of session otherwise
        it is not possible to delete project.
        """
        tmp_path = tmp_path / "test with space"

        test_project_name = "test_make_folders"

        project = test_utils.setup_project_default_configs(
            test_project_name,
            tmp_path,
            local_path=tmp_path / test_project_name,
        )

        cwd = os.getcwd()
        yield project
        test_utils.teardown_project(cwd, project)

    # ----------------------------------------------------------------------------------------------------------
    # Tests
    # ----------------------------------------------------------------------------------------------------------

    @pytest.mark.parametrize("prefix", ["sub", "ses"])
    @pytest.mark.parametrize(
        "input", [1, {"test": "one"}, 1.0, ["1", "2", ["three"]]]
    )
    def test_format_names_bad_input(self, input, prefix):
        """
        Test that names passed in incorrect type
        (not str, list) raise appropriate error.
        """
        with pytest.raises(BaseException) as e:
            formatting.format_names(input, prefix)

        assert (
            "Ensure subject and session names are "
            "list of strings, or string" == str(e.value)
        )

    @pytest.mark.parametrize("prefix", ["sub", "ses"])
    def test_format_names_duplicate_ele(self, prefix):
        """
        Test that appropriate error is raised when duplicate name
        is passed to format_names().
        """
        with pytest.raises(BaseException) as e:
            formatting.format_names(["1", "2", "3", "3", "4"], prefix)

        assert (
            "Subject and session names but all be unique "
            "(i.e. there are no duplicates in list input)." == str(e.value)
        )

    def test_duplicate_ses_or_sub_key_value_pair(self, project):
        """
        Test the check that if a duplicate key is attempt to be made
        when making a folder e.g. sub-001 exists, then make sub-001_id-123.
        After this check, make a folder that can be made (e.g. sub-003)
        just to make sure it does not raise error.

        Then, within an already made subject, try and make a session
        with a ses that already exists and check.
        """
        # Check trying to make sub only
        subs = ["sub-001_id-123", "sub-002_id-124"]
        project.make_sub_folders(subs)

        with pytest.raises(BaseException) as e:
            project.make_sub_folders("sub-001_id-125")

        assert (
            str(e.value) == "Cannot make folders. "
            "The key sub-001 already exists in the project"
        )

        project.make_sub_folders("sub-003")

        # check try and make ses within a sub
        sessions = ["ses-001_date-1605", "ses-002_date-1606"]
        project.make_sub_folders(subs, sessions)

        with pytest.raises(BaseException) as e:
            project.make_sub_folders("sub-001_id-123", "ses-002_date-1607")

        assert (
            str(e.value) == "Cannot make folders. "
            "The key ses-002 for sub-001_id-123 already exists in the project"
        )

        project.make_sub_folders("sub-001", "ses-003")

    def test_format_names_prefix(self):
        """
        Check that format_names correctly prefixes input
        with default sub or ses prefix. This is less useful
        now that ses/sub name dash and underscore order is
        more strictly checked.
        """
        prefix = "sub"

        # check name is prefixed
        formatted_names = formatting.format_names("1", prefix)
        assert formatted_names[0] == "sub-1"

        # check existing prefix is not duplicated
        formatted_names = formatting.format_names("sub-1", prefix)
        assert formatted_names[0] == "sub-1"

        # test mixed list of prefix and unprefixed are prefixed correctly.
        mixed_names = ["1", prefix + "-four", "5", prefix + "-6"]
        formatted_names = formatting.format_names(mixed_names, prefix)
        assert formatted_names == [
            "sub-1",
            "sub-four",
            "sub-5",
            "sub-6",
        ]

    def test_generate_folders_default_ses(self, project):
        """
        Make a subject folders with full tree. Don't specify
        session name (it will default to no sessions).

        Check that the folder tree is created correctly. Pass
        a dict that indicates if each subfolder is used (to avoid
        circular testing from the project itself).
        """
        subs = ["1_1", "sub-two", "3_3-3"]

        project.make_sub_folders(subs)

        test_utils.check_folder_tree_is_correct(
            project,
            base_folder=test_utils.get_rawdata_path(project),
            subs=["sub-1_1", "sub-two", "sub-3_3-3"],
            sessions=[],
            folder_used=test_utils.get_default_folder_used(),
        )

    def test_explicitly_session_list(self, project):
        """
        Perform an alternative test where the output is tested explicitly.
        This is some redundancy to ensure tests are working correctly and
        make explicit the expected folder tree.

        Note for new folders, this will have to be manually updated.
        This is highlighted in an assert in check_and_cd_folder()
        """
        subs = ["sub-001", "sub-002"]
        sessions = ["ses-001", "="]
        project.make_sub_folders(subs, sessions)
        base_folder = test_utils.get_rawdata_path(project)

        for sub in subs:
            for ses in ["ses-001", "ses-="]:
                test_utils.check_and_cd_folder(join(base_folder, sub, ses, "ephys"))
                test_utils.check_and_cd_folder(
                    join(
                        base_folder,
                        sub,
                        ses,
                        "behav",
                    )
                )
                test_utils.check_and_cd_folder(
                    join(base_folder, sub, ses, "funcimg")
                )
                test_utils.check_and_cd_folder(join(base_folder, sub, "histology"))

    @pytest.mark.parametrize(
        "dir_key", test_utils.get_default_folder_used().keys()
    )
    def test_turn_off_specific_folder_used(self, project, dir_key):
        """
        Whether or not a folder is made is held in the .used key of the
        folder class (stored in project.cfg.data_type_folders).
        """

        # Overwrite configs to make specified folder not used.
        project.update_config("use_" + dir_key, False)
        folder_used = test_utils.get_default_folder_used()
        folder_used[dir_key] = False

        # Make dir tree
        subs = ["sub-001", "sub-002"]
        sessions = ["ses-001", "ses-002"]
        project.make_sub_folders(subs, sessions)

        # Check dir tree is not made but all others are
        test_utils.check_folder_tree_is_correct(
            project,
            base_folder=test_utils.get_rawdata_path(project),
            subs=subs,
            sessions=sessions,
            folder_used=folder_used,
        )

    def test_custom_folder_names(self, project):
        """
        Change folder names to custom (non-default) and
        ensure they are made correctly.
        """
        # Change folder names to custom names
        project.cfg.data_type_folders["ephys"].name = "change_ephys"
        project.cfg.data_type_folders["behav"].name = "change_behav"
        project.cfg.data_type_folders["histology"].name = "change_histology"
        project.cfg.data_type_folders["funcimg"].name = "change_funcimg"

        # Make the folders
        sub = "sub-001"
        ses = "ses-001"
        project.make_sub_folders(sub, ses)

        # Check the folders were not made / made.
        base_folder = test_utils.get_rawdata_path(project)
        test_utils.check_and_cd_folder(
            join(
                base_folder,
                sub,
                ses,
                "change_ephys",
            )
        )
        test_utils.check_and_cd_folder(join(base_folder, sub, ses, "change_behav"))
        test_utils.check_and_cd_folder(join(base_folder, sub, ses, "change_funcimg"))

        test_utils.check_and_cd_folder(join(base_folder, sub, "change_histology"))

    @pytest.mark.parametrize(
        "files_to_test",
        [
            ["all"],
            ["ephys", "behav"],
            ["ephys", "behav", "histology"],
            ["ephys", "behav", "histology", "funcimg"],
            ["funcimg", "ephys"],
            ["funcimg"],
        ],
    )
    def test_data_types_subsection(self, project, files_to_test):
        """
        Check that combinations of data_types passed to make file dir
        make the correct combination of data types.

        Note this will fail when new top level dirs are added, and should be
        updated.
        """
        sub = "sub-001"
        ses = "ses-001"
        project.make_sub_folders(sub, ses, files_to_test)

        base_folder = test_utils.get_rawdata_path(project)

        # Check at the subject level
        sub_file_names = test_utils.glob_basenames(
            join(base_folder, sub, "*"),
            exclude=ses,
        )
        if "histology" in files_to_test:
            assert "histology" in sub_file_names
            files_to_test.remove("histology")

        # Check at the session level
        ses_file_names = test_utils.glob_basenames(
            join(base_folder, sub, ses, "*"),
            exclude=ses,
        )

        if files_to_test == ["all"]:
            assert ses_file_names == sorted(["ephys", "behav", "funcimg"])
        else:
            assert ses_file_names == sorted(files_to_test)

    def test_date_flags_in_session(self, project):
        """
        Check that @DATE@ is converted into current date
        in generated folder names
        """
        date, time_ = self.get_formatted_date_and_time()

        project.make_sub_folders(
            ["sub-001", "sub-002"],
            [f"ses-001_{tags('date')}", f"002_{tags('date')}"],
            "ephys",
        )

        ses_names = test_utils.glob_basenames(
            join(test_utils.get_rawdata_path(project), "**", "ses-*"),
            recursive=True,
        )

        assert all([date in name for name in ses_names])
        assert all([tags("date") not in name for name in ses_names])

    def test_datetime_flag_in_session(self, project):
        """
        Check that @DATETIME@ is converted to datetime
        in generated folder names
        """
        date, time_ = self.get_formatted_date_and_time()

        project.make_sub_folders(
            ["sub-001", "sub-002"],
            [f"ses-001_{tags('datetime')}", f"002_{tags('datetime')}"],
            "ephys",
        )

        ses_names = test_utils.glob_basenames(
            join(test_utils.get_rawdata_path(project), "**", "ses-*"),
            recursive=True,
        )

        # Convert the minutes to regexp as could change during test runtime
        regexp_time = r"\d\d\d\d\d\d"
        datetime_regexp = f"{date}_time-{regexp_time}"

        assert all([re.search(datetime_regexp, name) for name in ses_names])
        assert all([tags("time") not in name for name in ses_names])

    # ----------------------------------------------------------------------------------------------------------
    # Test Helpers
    # ----------------------------------------------------------------------------------------------------------

    def get_formatted_date_and_time(self):
        date = str(datetime.datetime.now().date())
        date = date.replace("-", "")
        time_ = datetime.datetime.now().time().strftime("%Hh%Mm")
        return date, time_