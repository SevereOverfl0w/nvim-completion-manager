# -*- coding: utf-8 -*-

# For debugging, use this command to start neovim:
#
# NVIM_PYTHON_LOG_FILE=nvim.log NVIM_PYTHON_LOG_LEVEL=INFO nvim
#
#
# Please register source before executing any other code, this allow cm_core to
# read basic information about the source without loading the whole module, and
# modules required by this module
from cm import register_source, getLogger, Base

register_source(name='cm-gocode',
                priority=9,
                abbreviation='Go',
                scoping=True,
                scopes=['go'],
                cm_refresh_patterns=[r'\.(\w*)$'],)

import re
import subprocess
import json

logger = getLogger(__name__)


class Source(Base):

    def __init__(self,nvim):
        super(Source,self).__init__(nvim)

    def cm_refresh(self,info,ctx,*args):

        # Note:
        # 
        # If you'r implementing you own source, and you want to get the content
        # of the file, Please use `cm.get_src()` instead of
        # `"\n".join(self._nvim.current.buffer[:])`

        src = self.get_src(ctx)

        # convert lnum, col to offset
        offset = self.get_pos(ctx['lnum'],ctx['col'],src)

        # invoke gocode
        proc = subprocess.Popen(args=['gocode','-f','json','autocomplete','%s' % offset], 
                                stdin=subprocess.PIPE, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.DEVNULL)

        result, errs = proc.communicate(src.encode('utf-8'),timeout=30)
        # result: [1, [{"class": "func", "name": "Print", "type": "func(a ...interface{}) (n int, err error)"}, ...]]
        result = json.loads(result.decode('utf-8')) 
        logger.info("result %s", result)
        completions = result[1]

        if not completions:
            return

        matches = []

        for complete in completions:

            # {
            #     "class": "func",
            #     "name": "Fprintln",
            #     "type": "func(w !io!io.Writer, a ...interface{}) (n int, err error)"
            # },

            item = dict(word=complete['name'],
                        icase=1,
                        dup=1,
                        menu=complete.get('type',''),
                        # info=complete.get('doc',''),
                        )

            matches.append(item)

            # snippet support
            if 'class' in complete and complete['class']=='func' and 'type' in complete:
                m = re.search(r'func\((.*?)\)',complete['type'])
                if not m:
                    continue
                params = m.group(1)
                params = params.split(',')
                logger.info('snippet params: %s',params)
                snip_params = []
                num = 1
                optional = ''
                for param in params:
                    param = param.strip()
                    if not param:
                        logger.error("failed to process snippet for item: %s, param: %s", item, param)
                        break
                    name = param.split(' ')[0]
                    if param.find('...')>=0:
                        # optional args
                        if num>1:
                            optional += '${%s:, %s...}' % (num, name)
                        else:
                            optional += '${%s:%s...}' % (num, name)
                        break
                    snip_params.append("${%s:%s}" % (num,name))
                    num += 1

                item['snippet'] = item['word'] + '(' + ", ".join(snip_params) + optional + ')${0}'

        logger.info('matches %s', matches)
        self.complete(info, ctx, ctx['startcol'], matches)

