package asymmetric.sign;

import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.pkcs.PKCS10CertificationRequest;

import java.security.Security;
import java.security.cert.X509Certificate;

public class AsymmetricMain {

    static void main(String[] args) {
        Security.addProvider(new BouncyCastleProvider());

        AsymmetricKeysCA asymmetricKeysCA = new AsymmetricKeysCA();
        AsymmetricKeysUser asymmetricKeysUser = new AsymmetricKeysUser();

        PKCS10CertificationRequest csr = asymmetricKeysUser.generateCSR();

        X509Certificate certificate = asymmetricKeysCA.signCertificate(csr);
        System.out.println("Certificate: " + certificate);


    }

}
