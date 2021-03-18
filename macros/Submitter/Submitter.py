import os, sys, math
import subprocess
from XMLInfo import *
from utils import *
from utils_submitter import *
from shutil import copy
import copy as cp
from collections import OrderedDict
from prettytable import PrettyTable
import shutil



class Submitter:
    def __init__(self, xmlfilename):
        self.xmlinfo = XMLInfo(xmlfilename)

        path_parts_local = [item for item in self.xmlinfo.xmlfilename.split('/')[:-1]]
        self.configdir = str(os.path.join('/', *path_parts_local))

        path_parts_local.append('workdir_%s' % (self.xmlinfo.xmlfilename.split('/')[-1][:-4]))
        self.workdir_local = str(os.path.join('/', *path_parts_local))

        path_parts_remote = [item for item in self.xmlinfo.configsettings.OutputDirectory.split('/')]
        path_parts_remote.append('workdir_%s' % (self.xmlinfo.xmlfilename.split('/')[-1][:-4]))
        self.workdir_remote = str(os.path.join('/', *path_parts_remote))

        self.missing_files_txt = os.path.join(self.workdir_local, 'commands_missing_files.txt')



    def Divide(self):
        print green('--> Dividing and preparing jobs')

        # First create local and remote (potentially T3) workdir. Inside, create folders for each sample to store the small XML and root files
        self.create_local_workdir()
        self.create_remote_workdir()
        njobs_and_type_per_dataset = self.divide_xml_files()
        self.write_expected_files(njobs_and_type_per_dataset=njobs_and_type_per_dataset)
        self.Output()



    def Submit(self):
        print green('--> Submitting jobs')

        missing_files_per_dataset = self.Output()

        # njobs = -1
        # with open(self.missing_files_txt, 'r') as f:
        #     njobs = len(f.readlines())
        for datasetname in missing_files_per_dataset:
            missing_files = os.path.join(self.workdir_local, datasetname, 'commands_missing_files.txt')
            with open(missing_files, 'r') as f:
                njobs = len(f.readlines())
            if njobs < 1: continue
            environ_path = os.getenv('PATH')
            environ_ld_lib_path = os.getenv('LD_LIBRARY_PATH')
            command = 'sbatch -a 1-%i -J %s -p quick --chdir %s -t 01:00:00 submit_analyzer_command.sh %s %s %s' % (njobs, datasetname, os.path.join(self.workdir_local, datasetname, 'joboutput'), missing_files, environ_path, environ_ld_lib_path)
            jobid = int(subprocess.check_output(command.split(' ')).rstrip('\n').split(' ')[-1])
            print green('  --> Submitted array of %i jobs for dataset %s. JobID: %i' % (njobs, datasetname, jobid))





    def Output(self):
        print green('--> Checking outputs and updating list of missing files')

        expected_files = self.read_expected_files()
        missing_files_per_dataset = self.find_missing_files(expected_files=expected_files)
        missing_files_all = []
        for datasetname in missing_files_per_dataset:
            # for item in missing_files_per_dataset[datasetname]:
            #     missing_files_all.append(item)
            commands = [self.get_command_for_file(filename_expected=filename_expected) for filename_expected in missing_files_per_dataset[datasetname]]
            with open(os.path.join(self.workdir_local, datasetname, 'commands_missing_files.txt'), 'wr') as f:
                for command in commands:
                    f.write(command + '\n')

        # print information on missing files to shell
        print '\n\n'
        print green('  Status report of job processing')
        print green('  ===============================\n')


        table = PrettyTable(['Sample', 'Processed files'])
        table.align['Sample'] = 'l'
        table.align['Processed files'] = 'l'
        nmissing_total = 0
        nexpected_total = 0
        for datasetname in missing_files_per_dataset:
            table.add_row([datasetname, '(%i / %i)' % (len(expected_files[datasetname]) - len(missing_files_per_dataset[datasetname]), len(expected_files[datasetname]))])
            nmissing_total += len(missing_files_per_dataset[datasetname])
            nexpected_total += len(expected_files[datasetname])


        print green(table)
        total = '(%i / %i)' % (nexpected_total - nmissing_total, nexpected_total)
        tb_widths = table._widths
        print green('| Total' + ' ' * (tb_widths[0] - len('Total') ) + ' | ' + total + ' ' * (tb_widths[1] - len(total) ) + ' |')
        print green('+-' + '-' * tb_widths[0] + '-+-' + '-' * tb_widths[1] + '-+')
        print '\n\n'
        return missing_files_per_dataset



    def Clean(self):
        print green('--> Cleaning up (removing) local and remote workdir')

        shutil.rmtree(self.workdir_local, ignore_errors=True)
        shutil.rmtree(self.workdir_remote, ignore_errors=True)
        print green('--> Cleaned up (removed) local and remote workdir')


    def Add(self, force=False):
        print green('--> Adding finished samples')

        # update list of missing files
        self.Output()

        # find datasets that are already done
        datasetnames_complete = []
        expected_files = self.read_expected_files()
        missing_files = self.find_missing_files(expected_files=expected_files)
        for datasetname in missing_files:
            if len(missing_files[datasetname]) == 0:
                datasetnames_complete.append(datasetname)


        # add all completed datasets
        commands = []
        for datasetname in datasetnames_complete:

            # get list of expected files
            expected_files_string = ' '.join(expected_files[datasetname])


            # get outfilename
            outfilename_parts = expected_files[datasetname][0].split('/')[-1].split('_')[:-1]
            outfilename = '_'.join(outfilename_parts) + '.root'
            outpath_parts = self.workdir_remote.split('/')[:-1]
            outpath = str(os.path.join('/', *outpath_parts))
            outfilepath_and_name = os.path.join(outpath, outfilename)

            if os.path.isfile(outfilepath_and_name) and not force:
                continue

            command = 'hadd'
            if force: command += ' -f'
            command += ' %s' % (outfilepath_and_name)
            command += ' ' + expected_files_string
            commands.append(command)

        execute_commands_parallel(commands)

        if force:
            print green('--> Added all completed files (%i)' % (len(commands)))
        else:
            print green('--> Added newly completed files, if any (%i)' % (len(commands)))



    def Hadd(self):
        print green('--> Hadding samples into groups. Assuming all samples have been processed entirely.')

        # update list of missing files
        # self.Output()

        datasets_per_group = OrderedDict()
        for ds in self.xmlinfo.datasets:
            datasetname = str(ds.settings.Name)
            group = str(ds.settings.Group)
            datasettype = str(ds.settings.Type)
            if group in datasets_per_group:
                datasets_per_group[group][1].append(datasetname)
            else:
                datasets_per_group[group] = (datasettype, [datasetname])

        commands = []
        for group in datasets_per_group:
            if group == 'None': continue # don't hadd if files are not part of a group
            grouptype = datasets_per_group[group][0]
            outfilename = '%s__%s.root' % (grouptype, group)
            outpath_parts = self.workdir_remote.split('/')[:-1]
            outpath = str(os.path.join('/', *outpath_parts))
            outfilepath_and_name = os.path.join(outpath, outfilename)
            sourcestring = ' '.join( [os.path.join(outpath,  '%s__%s.root' % (grouptype, filename)) for filename in datasets_per_group[group][1]] )

            command = 'hadd -f %s %s' % (outfilepath_and_name, sourcestring)
            commands.append(command)
        execute_commands_parallel(commands)
        print green('--> Added %i datasets into groups.' % (len(commands)))















    # smaller functions to keep main part clean


    def create_local_workdir(self):
        """ Create workdir + 1 subdir per sample for Submitter in the local config/ directory on the same level as the XML file """

        ensureDirectory(self.workdir_local)
        for dataset in self.xmlinfo.datasets:
            samplename = dataset.settings.Name
            ensureDirectory(os.path.join(self.workdir_local, samplename))

            # copy .dtd file
            copy(os.path.join(self.configdir, 'Configuration.dtd'), os.path.join(self.workdir_local, samplename))
        print green('  --> Created local workdir \'%s\'' % (self.workdir_local))


    def create_remote_workdir(self):
        """ Create workdir + 1 subdir per sample for Submitter in the remote target directory """

        ensureDirectory(self.workdir_remote)
        for dataset in self.xmlinfo.datasets:
            samplename = dataset.settings.Name
            ensureDirectory(os.path.join(self.workdir_remote, samplename))
        print green('  --> Created remote workdir \'%s\'' % (self.workdir_remote))

    def divide_xml_files(self):
        """ From the main XML file, create a number of smaller ones, one per job to be submitted and divided by sample. """

        # check how to split jobs
        nfiles_per_job  = int(self.xmlinfo.submissionsettings.FilesPerJob)
        nevents_per_job = int(self.xmlinfo.submissionsettings.EventsPerJob)
        is_filesplit  = False
        is_eventsplit = False
        if nfiles_per_job > 0: is_filesplit = True
        if nevents_per_job > 0: is_eventsplit = True

        if (not is_filesplit and not is_eventsplit) or (is_filesplit and is_eventsplit):
            raise ValueError(red('In the XML file, either both or neither of "EventsPerJob" and "FilesPerJob" is >0. This is not supported, please choose one of the two options to split jobs.'))

        # all_datasets = deepcopy(self.xmlinfo.datasets)

        # handle filesplit
        njobs_and_type_per_dataset = OrderedDict()
        if is_filesplit:
            for dataset in self.xmlinfo.datasets:
                datasetname = str(dataset.settings.Name)
                print green('    --> Dividing sample %s' % (datasetname))
                njobs_this_dataset = 0
                nfiles = len(dataset.infiles)
                njobs = int(math.ceil(nfiles/float(nfiles_per_job)))
                for i in range(njobs):
                    self.write_single_xml(datasetname=datasetname, index=i+1, nfiles_per_job=nfiles_per_job)
                    # self.xmlinfo.datasets = all_datasets
                    njobs_this_dataset += 1
                njobs_and_type_per_dataset[datasetname] = (njobs_this_dataset, str(dataset.settings.Type))

        # handle eventsplit
        else:
            for dataset in self.xmlinfo.datasets:
                datasetname = str(dataset.settings.Name)
                print green('    --> Dividing sample %s' % (datasetname))
                njobs_this_dataset = 0
                nevents = get_number_events_in_dataset(dataset=dataset)
                njobs = int(math.ceil(nevents/float(nevents_per_job)))
                for i in range(njobs):
                    self.write_single_xml(datasetname=datasetname, index=i+1, nevents_per_job=nevents_per_job)
                    # self.xmlinfo.datasets = all_datasets
                    njobs_this_dataset += 1
                njobs_and_type_per_dataset[datasetname] = (njobs_this_dataset, str(dataset.settings.Type))

        print green('  --> Divided XML files')
        return njobs_and_type_per_dataset


    def write_expected_files(self, njobs_and_type_per_dataset):
        """ Create a txt file, containing a list of samples to be expected according to the given split settings. Uses return-value of divide_xml_files()."""

        for datasetname in njobs_and_type_per_dataset:
            njobs = njobs_and_type_per_dataset[datasetname][0]
            datasettype = njobs_and_type_per_dataset[datasetname][1]

            outpath = os.path.join(self.workdir_remote, datasetname)
            expected_files = []
            for i in range(njobs):
                filename = '%s__%s_%i.root\n' % (datasettype, datasetname, i+1)
                expected_files.append(os.path.join(outpath, filename))

            outfilename = os.path.join(self.workdir_local, datasetname, 'expected_files.txt')
            with open(outfilename, 'wr') as f:
                for file in expected_files:
                    f.write(file)

            sampleworkdir = os.path.join(self.workdir_local, datasetname, 'joboutput')
            ensureDirectory(sampleworkdir)

        print green('  --> Wrote list of expected files')











    def write_single_xml(self, datasetname, index, nfiles_per_job=-1, nevents_per_job=-1):

        if nfiles_per_job <= 0 and nevents_per_job <= 0:
            raise ValueError(red('It seems like the new XML files should be written neither in filesplit nor eventsplit mode. Exit.'))
        if nfiles_per_job > 0 and nevents_per_job > 0:
            raise ValueError(red('It seems like the new XML files should be written both in filesplit and eventsplit mode. Exit.'))


        outfilename = os.path.join(self.workdir_local, datasetname, '%s_%i.xml' % (datasetname, index))\

        # throw away all other datasets but the one we specified as a parameter here
        self.xmlinfo.datasets_to_write = [deepcopy(ds) for ds in self.xmlinfo.datasets if ds.settings.Name == datasetname]
        if len(self.xmlinfo.datasets_to_write) != 1:
            raise ValueError(red('Found != 1 datasets with name \'%s\'' % (datasetname)))


        # filesplit mode
        if nfiles_per_job > 0:

            # remove most infiles from the one dataset selected above: keep only those we want in this small xml file
            fileindex_start = (index-1) * nfiles_per_job
            fileindex_stop  = fileindex_start + nfiles_per_job
            self.xmlinfo.datasets_to_write[0].infiles = self.xmlinfo.datasets_to_write[0].infiles[fileindex_start:fileindex_stop]

        # eventsplit mode
        else:

            # only need to specify nevents_max and _skip in the xml file
            self.xmlinfo.configsettings.NEventsSkip = str((index-1) * nevents_per_job)
            self.xmlinfo.configsettings.NEventsMax  = str(nevents_per_job)

        # adjust general settings: output path, postfix
        self.xmlinfo.configsettings.OutputDirectory = os.path.join(self.workdir_remote, datasetname)
        self.xmlinfo.configsettings.PostFix         = '_%i' % (index)

        # write new xml file
        with open(outfilename, 'wr') as f:

            # header
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<!DOCTYPE Configuration PUBLIC "" "Configuration.dtd"[]>\n')

            # main body (everything except for header)
            f.write(self.xmlinfo.get_XML_document().toprettyxml())


    def read_expected_files(self):

        files_per_dataset = OrderedDict()
        for dataset in self.xmlinfo.datasets:
            datasetname = str(dataset.settings.Name)
            infilename = os.path.join(self.workdir_local, datasetname, 'expected_files.txt')

            with open(infilename, 'r') as f:
                lines = f.readlines()
            filenames_expected = []
            for filename in lines:
                if filename.endswith('\n'):
                    filenames_expected.append(filename[:-len('\n')])
            files_per_dataset[datasetname] = filenames_expected
        return files_per_dataset


    def find_missing_files(self, expected_files):

        missing_files_per_dataset = OrderedDict()
        # nmissing_per_dataset = OrderedDict()
        for datasetname in expected_files:
            nmissing = 0
            missing = []
            for file in expected_files[datasetname]:
                result = subprocess.Popen(['ls', file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output = result.communicate()[0]
                returncode = result.returncode
                if returncode > 0: # opening failed
                    missing.append(file)
                    nmissing += 1
            missing_files_per_dataset[datasetname] = missing
            # nmissing_per_dataset[datasetname] = nmissing
        return missing_files_per_dataset



    def get_command_for_file(self, filename_expected):

        datasetname = filename_expected.split('/')[-2]
        xmlfilename = filename_expected.split('/')[-1].split('__')[1].replace('.root', '.xml')
        fullxmlfilename = os.path.join(self.workdir_local, datasetname, xmlfilename)
        command = 'Analyzer %s' % (fullxmlfilename)
        return command



















#