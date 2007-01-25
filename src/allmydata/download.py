
import os, sha
from zope.interface import implements
from twisted.python import failure, log
from twisted.internet import defer
from twisted.application import service

from allmydata.util import idlib, bencode
from allmydata.util.deferredutil import DeferredListShouldSucceed
from allmydata import codec
from allmydata.uri import unpack_uri
from allmydata.interfaces import IDownloadTarget, IDownloader

class NotEnoughPeersError(Exception):
    pass

class HaveAllPeersError(Exception):
    # we use this to jump out of the loop
    pass

class FileDownloader:
    debug = False

    def __init__(self, peer, uri):
        self._peer = peer
        (codec_name, codec_params, verifierid) = unpack_uri(uri)
        assert isinstance(verifierid, str)
        assert len(verifierid) == 20
        self._verifierid = verifierid
        self._decoder = codec.get_decoder_by_name(codec_name)
        self._decoder.set_serialized_params(codec_params)
        self.needed_shares = self._decoder.get_required_shares()

    def set_download_target(self, target):
        self._target = target
        self._target.register_canceller(self._cancel)

    def _cancel(self):
        pass

    def start(self):
        log.msg("starting download [%s]" % (idlib.b2a(self._verifierid),))
        if self.debug:
            print "starting download"
        # first step: who should we download from?

        # maybe limit max_peers to 2*len(self.shares), to reduce memory
        # footprint
        max_peers = None

        self.permuted = self._peer.permute_peerids(self._verifierid, max_peers)
        for p in self.permuted:
            assert isinstance(p, str)
        self.landlords = [] # list of (peerid, bucket_num, remotebucket)

        d = defer.maybeDeferred(self._check_next_peer)
        d.addCallback(self._got_all_peers)
        return d

    def _check_next_peer(self):
        if len(self.permuted) == 0:
            # there are no more to check
            raise NotEnoughPeersError
        peerid = self.permuted.pop(0)

        d = self._peer.get_remote_service(peerid, "storageserver")
        def _got_peer(service):
            bucket_num = len(self.landlords)
            if self.debug: print "asking %s" % idlib.b2a(peerid)
            d2 = service.callRemote("get_buckets", verifierid=self._verifierid)
            def _got_response(buckets):
                if buckets:
                    bucket_nums = [num for (num,bucket) in buckets]
                    if self.debug:
                        print " peerid %s has buckets %s" % (idlib.b2a(peerid),
                                                             bucket_nums)

                    self.landlords.append( (peerid, buckets) )
                if len(self.landlords) >= self.needed_shares:
                    if self.debug: print " we're done!"
                    raise HaveAllPeersError
                # otherwise we fall through to search more peers
            d2.addCallback(_got_response)
            return d2
        d.addCallback(_got_peer)

        def _done_with_peer(res):
            if self.debug: print "done with peer %s:" % idlib.b2a(peerid)
            if isinstance(res, failure.Failure):
                if res.check(HaveAllPeersError):
                    if self.debug: print " all done"
                    # we're done!
                    return
                if res.check(IndexError):
                    if self.debug: print " no connection"
                else:
                    if self.debug: print " other error:", res
            else:
                if self.debug: print " they had data for us"
            # we get here for either good peers (when we still need more), or
            # after checking a bad peer (and thus still need more). So now we
            # need to grab a new peer.
            return self._check_next_peer()
        d.addBoth(_done_with_peer)
        return d

    def _got_all_peers(self, res):
        all_buckets = []
        for peerid, buckets in self.landlords:
            all_buckets.extend(buckets)
        # TODO: try to avoid pulling multiple shares from the same peer
        all_buckets = all_buckets[:self.needed_shares]
        # retrieve all shares
        dl = []
        shares = []
        for (bucket_num, bucket) in all_buckets:
            d0 = bucket.callRemote("get_metadata")
            d1 = bucket.callRemote("read")
            d2 = DeferredListShouldSucceed([d0, d1])
            def _got(res):
                sharenum_s, sharedata = res
                sharenum = bencode.bdecode(sharenum_s)
                shares.append((sharenum, sharedata))
            d2.addCallback(_got)
            dl.append(d2)
        d = DeferredListShouldSucceed(dl)

        d.addCallback(lambda res: self._decoder.decode(shares))

        def _write(decoded_shares):
            data = "".join(decoded_shares)
            self._target.open()
            hasher = sha.new(netstring("allmydata_v1_verifierid"))
            hasher.update(data)
            vid = hasher.digest()
            assert self._verifierid == vid, "%s != %s" % (idlib.b2a(self._verifierid), idlib.b2a(vid))
            self._target.write(data)
        d.addCallback(_write)

        def _done(res):
            self._target.close()
            return self._target.finish()
        def _fail(res):
            self._target.fail()
            return res
        d.addCallbacks(_done, _fail)
        return d

def netstring(s):
    return "%d:%s," % (len(s), s)

class FileName:
    implements(IDownloadTarget)
    def __init__(self, filename):
        self._filename = filename
    def open(self):
        self.f = open(self._filename, "wb")
        return self.f
    def write(self, data):
        self.f.write(data)
    def close(self):
        self.f.close()
    def fail(self):
        self.f.close()
        os.unlink(self._filename)
    def register_canceller(self, cb):
        pass # we won't use it
    def finish(self):
        pass

class Data:
    implements(IDownloadTarget)
    def __init__(self):
        self._data = []
    def open(self):
        pass
    def write(self, data):
        self._data.append(data)
    def close(self):
        self.data = "".join(self._data)
        del self._data
    def fail(self):
        del self._data
    def register_canceller(self, cb):
        pass # we won't use it
    def finish(self):
        return self.data

class FileHandle:
    implements(IDownloadTarget)
    def __init__(self, filehandle):
        self._filehandle = filehandle
    def open(self):
        pass
    def write(self, data):
        self._filehandle.write(data)
    def close(self):
        # the originator of the filehandle reserves the right to close it
        pass
    def fail(self):
        pass
    def register_canceller(self, cb):
        pass
    def finish(self):
        pass

class Downloader(service.MultiService):
    """I am a service that allows file downloading.
    """
    implements(IDownloader)
    name = "downloader"
    debug = False

    def download(self, uri, t):
        assert self.parent
        assert self.running
        t = IDownloadTarget(t)
        assert t.write
        assert t.close
        dl = FileDownloader(self.parent, uri)
        dl.set_download_target(t)
        if self.debug:
            dl.debug = True
        d = dl.start()
        return d

    # utility functions
    def download_to_data(self, uri):
        return self.download(uri, Data())
    def download_to_filename(self, uri, filename):
        return self.download(uri, FileName(filename))
    def download_to_filehandle(self, uri, filehandle):
        return self.download(uri, FileHandle(filehandle))


